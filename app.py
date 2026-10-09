"""Streamlit interface for the SkillGraph Etapa 1 MVP."""

from __future__ import annotations

import html
import os
import time
import uuid
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

from typing import Any

import pandas as pd
from src.resume_extractor import ResumeExtractionError, extract_pdf_text
from src.agents.runtime import run_agent_flow, run_agent_turn
from src.agents.router import route_turn
import streamlit as st
import streamlit.components.v1 as components
from src.answer_router import (
    answer_comparison_question,
    answer_competency_question,
    answer_smalltalk_question,
    answer_structured_question,
)
from src.dify_client import DifyClient, DifyClientError


def stream_production_rag(query: str, conversation_id: str = ""):
    """Yield production Dify Chatflow events without a backend wrapper."""

    client = DifyClient.from_environment()
    yield from client.stream_chat(query, conversation_id=conversation_id)


from src.feedback import FeedbackStore
from src.intent_router import Intent, route_question
from src.monitoring import record_event
from src.observability import OBSERVABILITY, TraceContext
from src.reasoning import route_steps
from src.toxicity import safe_response
from src.security import UserRole, evaluate_input
from src.privacy_ui import upload_privacy_notice
from src.session_store import SessionStore
from src.sql_tools import SQLToolError, SkillGraphDatabase
from src.ml_assistant import LocalMLAssistant, MLAssistantError
from src.ml_pipeline import ARTIFACT_NAME, global_explanation
from src.progress_ui import ResumeProgress
from src.error_ui import render_error_panel

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")
LOG_PATH = PROJECT_ROOT / "logs" / "skillgraph.jsonl"
STATE_DIR = PROJECT_ROOT / "state"
store = SessionStore(STATE_DIR / "skillgraph.sqlite")
feedback_store = FeedbackStore(STATE_DIR / "feedback.sqlite")


def _sources_from_event(event: object) -> list[dict[str, str]]:
    if not isinstance(event, dict):
        return []

    metadata: Any = event.get("metadata")
    if isinstance(metadata, dict) and isinstance(metadata.get("metadata"), dict):
        metadata = metadata["metadata"]
    if not isinstance(metadata, dict):
        return []

    resources = metadata.get("retriever_resources") or metadata.get("sources") or []
    if not isinstance(resources, list):
        return []
    return [
        {
            "document": str(
                item.get("document_name") or item.get("title") or item.get("name") or ""
            ),
            "content": str(item.get("content") or ""),
        }
        for item in resources
        if isinstance(item, dict)
    ]


def _deduplicate_sources(
    sources: list[dict[str, str]],
) -> list[dict[str, str]]:
    unique: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for source in sources:
        key = (source.get("document", ""), source.get("content", ""))
        if key not in seen:
            seen.add(key)
            unique.append(source)
    return unique


def _render_sources(sources: list[dict[str, str]]) -> None:
    unique = _deduplicate_sources(sources)
    if not unique:
        return
    with st.expander("Fontes recuperadas"):
        for source in unique:
            st.markdown(f"**{source.get('document') or 'Documento não identificado'}**")
            if source.get("content"):
                st.caption(source["content"][:600])


def _title_from_question(question: str) -> str:
    """Create a short topic label instead of copying the user's question."""

    normalized = " ".join(question.lower().split())
    patterns = (
        (
            ("carga horária", "carga horaria", "horas de treinamento"),
            "Comparação de carga horária entre cargos",
        ),
        (
            ("competências", "competencias", "lacunas"),
            "Indicadores de lacunas de competências",
        ),
        (
            ("treinamentos", "treinamento", "cursos"),
            "Catálogo e recomendações de treinamentos",
        ),
        (
            ("trilha", "trilhas", "desenvolvimento"),
            "Trilhas de desenvolvimento profissional",
        ),
        (
            ("política", "politica", "elegibilidade", "reembolso"),
            "Políticas de treinamento",
        ),
        (
            ("cargo", "cargos", "requisitos", "senioridade"),
            "Requisitos e competências de cargos",
        ),
        (("risco de lacuna", "diagnóstico"), "Consulta de diagnóstico de competências"),
    )
    for keywords, title in patterns:
        if any(keyword in normalized for keyword in keywords):
            return title
    return "Consulta sobre desenvolvimento profissional"


def _title_for_route(route: str, question: str = "") -> str:
    route_titles = {
        "resume_analysis": "Análise de currículo",
        "ml_prediction": "Recomendação de trilhas de competências",
        "gap_analysis": "Diagnóstico de lacunas de competências",
        "training_recommendation": "Recomendações de treinamentos",
        "policy_rag": "Políticas de treinamento",
        "structured_data": "Consulta de dados estruturados",
    }
    return route_titles.get(route, _title_from_question(question))


def _migrate_conversation_title(conversation: dict[str, Any]) -> None:
    """Replace generic legacy titles using the first message route."""

    title = conversation.get("title", "")
    generic_titles = {"Nova conversa", "Consulta sobre desenvolvimento profissional"}
    if title and title not in generic_titles and not title.endswith("…"):
        return
    messages = store.messages(conversation["id"], role=role)
    first = next((item for item in messages if item["role"] == "user"), None)
    if first:
        new_title = _title_for_route(first.get("route", ""), first.get("content", ""))
        if new_title != title:
            store.rename_conversation(conversation["id"], new_title, role=role)


def _ensure_resume_conversation(question: str, role: str) -> str:
    """Create/select a conversation with the explicit resume-analysis title."""
    conversation_id = st.session_state.get("active_conversation_id")
    if not conversation_id:
        conversation_id = store.create_conversation(
            "Análise de currículo", "crewai", role=role
        )
        st.session_state.active_conversation_id = conversation_id
    else:
        store.set_title(conversation_id, "Análise de currículo", role=role)
    return conversation_id


def _render_feedback(message: dict[str, Any]) -> None:
    message_id = message.get("id")
    if not message_id:
        return
    if feedback_store.get(message_id):
        st.caption("Feedback registrado. Obrigado!")
        return

    cols = st.columns([1, 1, 8])
    if cols[0].button("👍", key=f"positive-{message_id}", help="Resposta útil"):
        st.session_state[f"feedback_pending_{message_id}"] = 1
        st.rerun()
    if cols[1].button(
        "👎", key=f"negative-{message_id}", help="Resposta precisa melhorar"
    ):
        st.session_state[f"feedback_pending_{message_id}"] = -1
        st.rerun()

    pending = st.session_state.get(f"feedback_pending_{message_id}")
    if pending:
        comment = st.text_input(
            "Comentário opcional", key=f"feedback-comment-{message_id}"
        )
        if st.button("Enviar feedback", key=f"feedback-submit-{message_id}"):
            feedback_store.save(
                message_id,
                pending,
                route=message.get("route", ""),
                comment=comment,
                trace_id=message.get("trace_id", ""),
            )
            if message.get("trace_id"):
                OBSERVABILITY.record_feedback(
                    trace_id=message["trace_id"],
                    message_id=message_id,
                    rating=pending,
                    route=message.get("route", ""),
                )
            st.session_state.pop(f"feedback_pending_{message_id}", None)
            st.rerun()


def _speak(text: str) -> None:
    safe = html.escape(text).replace("\n", " ").replace("'", "\\'")
    components.html(
        "<script>window.speechSynthesis.cancel();"
        f"window.speechSynthesis.speak(new SpeechSynthesisUtterance('{safe}'));"
        "</script>",
        height=0,
    )


def _render_public_reasoning(
    route: str, steps: list[dict[str, Any]] | None = None, *, key: str = ""
) -> None:
    """Show public structured reasoning, never private chain-of-thought."""

    public_steps = steps or route_steps(route)
    with st.expander("Raciocínio estruturado do agente", expanded=False):
        for reasoning_step in public_steps:
            st.markdown(f"**{reasoning_step['stage']}** — {reasoning_step['summary']}")
            if reasoning_step.get("tool"):
                st.caption(f"Agente/ferramenta: {reasoning_step['tool']}")


def _format_resume_profile(
    profile: dict[str, Any] | None,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Prepare sanitized profile data for structured UI tables."""
    profile = profile or {}

    def rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        for item in items or []:
            level = item.get("level")
            result.append(
                {
                    "Competência": item.get("name")
                    or item.get("normalized_name")
                    or "Não identificada",
                    "Nível": (
                        f"{level:g}/5"
                        if isinstance(level, (int, float))
                        else "Não determinável"
                    ),
                    "Confiança": (
                        f"{float(item['confidence']):.0%}"
                        if isinstance(item.get("confidence"), (int, float))
                        else "Não informada"
                    ),
                    "Evidência": str(
                        item.get("evidence") or "Evidência insuficiente no currículo"
                    ),
                }
            )
        return result

    return (
        pd.DataFrame(rows(profile.get("skills", []))),
        pd.DataFrame(rows(profile.get("unrecognized_skills", []))),
        list(profile.get("missing_information", [])),
    )


def _render_resume_profile(profile: dict[str, Any] | None) -> None:
    """Render the structured resume result before the prose synthesis."""
    if not profile:
        return
    recognized, unknown, missing = _format_resume_profile(profile)
    st.subheader("Competências e habilidades identificadas")
    if recognized.empty:
        st.info("Nenhuma competência pôde ser estruturada com evidência suficiente.")
    else:
        st.dataframe(recognized, hide_index=True, use_container_width=True)
    with st.expander(
        "Competências não reconhecidas ou com nível incerto", expanded=not unknown.empty
    ):
        if unknown.empty:
            st.caption(
                "Nenhuma competência adicional foi classificada como desconhecida."
            )
        else:
            st.dataframe(unknown, hide_index=True, use_container_width=True)
    with st.expander("Informações ausentes ou que exigem confirmação", expanded=False):
        if missing:
            for item in missing:
                st.markdown(f"- {item}")
        else:
            st.caption("Nenhuma informação adicional foi sinalizada.")


def _render_ml_page() -> None:

    st.header("Desenvolvimento de competências com Machine Learning")
    st.caption(
        "Recomendação de trilhas para colaboradores informados por analistas e gestores de RH."
    )
    st.info(
        "Contexto: classificação multiclasse de trilhas tech. O sistema estima quais trilhas são mais compatíveis com as competências de um colaborador e aponta prioridades de desenvolvimento."
    )
    artifact_path = PROJECT_ROOT / ".ml_artifacts" / ARTIFACT_NAME
    if not artifact_path.exists():
        st.warning(
            "O modelo de competências ainda não foi preparado. Solicite ao administrador a execução do pipeline da Etapa 2."
        )
        return
    st.subheader("Recomende uma trilha para um colaborador")
    st.caption(
        "Descreva o colaborador sem nome, CPF, e-mail ou outros identificadores. Ex.: colaborador da equipe de dados."
    )
    assistant = LocalMLAssistant(artifact_path)
    for message in st.session_state.get("ml_messages", []):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    ml_question = st.chat_input(
        "Ex.: o colaborador tem Python avançado, SQL intermediário e está começando em IA generativa. Qual trilha priorizar?",
        key="ml-chat-input",
    )
    if ml_question:
        st.session_state.setdefault("ml_messages", []).append(
            {"role": "user", "content": ml_question}
        )
        with st.chat_message("user"):
            st.markdown(ml_question)
        with st.chat_message("assistant"):
            try:
                _render_public_reasoning("ml_prediction")
                result = assistant.predict_from_question(ml_question)
                st.markdown(result.answer)
                if result.recommendations:
                    st.dataframe(
                        pd.DataFrame(result.recommendations),
                        hide_index=True,
                        use_container_width=True,
                    )
                if role == UserRole.DESENVOLVEDOR.value and result.profile:
                    with st.expander("Explicabilidade técnica", expanded=False):
                        from src.xai_diagnostics import model_diagnostics

                        structured = result.structured or {}
                        diagnostics = model_diagnostics(artifact_path)
                        st.subheader("Qualidade da entrada")
                        quality = structured.get("input_quality", {})
                        st.json(
                            {
                                "competências reconhecidas": quality.get(
                                    "recognized_count",
                                    len(structured.get("recognized_skills", [])),
                                ),
                                "competências não reconhecidas": quality.get(
                                    "unrecognized_count",
                                    len(structured.get("unrecognized_skills", [])),
                                ),
                                "cobertura": quality.get("coverage", None),
                                "desconhecidas afetam o modelo": False,
                            }
                        )
                        st.subheader("Métricas do modelo")
                        st.caption(diagnostics["generalization_message"])
                        st.dataframe(
                            pd.DataFrame(diagnostics["validation"]),
                            hide_index=True,
                            use_container_width=True,
                        )
                        st.dataframe(
                            pd.DataFrame(diagnostics["test"]),
                            hide_index=True,
                            use_container_width=True,
                        )
                        st.subheader("Explicabilidade")
                        st.caption(diagnostics["global_xai_message"])
                        st.caption(diagnostics["association_message"])
                        st.caption(diagnostics["fairness_message"])
                        st.json(
                            {
                                "incerteza": structured.get("uncertainty", {}),
                                "explicações locais": structured.get(
                                    "local_explanations", []
                                ),
                                "prioridades": result.priorities,
                            }
                        )
                        try:
                            global_rows = global_explanation(artifact_path)
                            if global_rows:
                                st.dataframe(
                                    pd.DataFrame(global_rows),
                                    hide_index=True,
                                    use_container_width=True,
                                )
                            else:
                                st.info(
                                    "O modelo atual não fornece importâncias globais positivas para exibição."
                                )
                        except Exception as exc:
                            st.info(
                                "Explicação global indisponível para este artefato."
                            )
                            st.caption(str(exc)[:240])
                st.session_state["ml_messages"].append(
                    {"role": "assistant", "content": result.answer}
                )
            except MLAssistantError as exc:
                st.error(str(exc))
                st.session_state["ml_messages"].append(
                    {"role": "assistant", "content": str(exc)}
                )


def _render_manager_chart(
    frame: pd.DataFrame, *, value_column: str | None = None
) -> None:
    """Render a compact horizontal bar chart without extra dependencies."""
    if frame.empty:
        return
    numeric = [
        column
        for column in frame.columns
        if pd.api.types.is_numeric_dtype(frame[column])
    ]
    if not numeric:
        return
    selected = value_column if value_column in numeric else numeric[0]
    chart_frame = frame.set_index(frame.columns[0])[[selected]].copy()
    chart_frame.columns = ["valor"]
    chart_frame["valor"] = pd.to_numeric(chart_frame["valor"], errors="coerce").fillna(
        0
    )
    maximum = max(float(chart_frame["valor"].max()), 1.0)
    bars = []
    for label, value in chart_frame["valor"].items():
        width = max(2.0, float(value) / maximum * 100)
        bars.append(
            "<div style='display:flex;align-items:center;gap:8px;margin:6px 0'>"
            f"<span style='width:160px;overflow:hidden;text-overflow:ellipsis'>"
            f"{html.escape(str(label))}</span>"
            f"<div style='background:#16A34A;height:18px;width:{width:.1f}%;border-radius:4px'></div>"
            f"<strong>{float(value):.1f}</strong></div>"
        )
    st.markdown("".join(bars), unsafe_allow_html=True)


def _render_grouped_manager_chart(
    frame: pd.DataFrame, label_column: str, value_columns: list[str]
) -> None:
    """Render multiple aggregate series with a legend."""
    if frame.empty or not value_columns:
        return
    colors = ["#16A34A", "#DC2626", "#2563EB", "#F59E0B"]
    maximum = max(
        float(
            pd.to_numeric(frame[value_columns], errors="coerce")
            .fillna(0)
            .to_numpy()
            .max()
        ),
        1.0,
    )
    legend = " ".join(
        f"<span style='margin-right:12px'><i style='background:{colors[i]};display:inline-block;width:10px;height:10px;border-radius:50%'></i> {html.escape(column)}</span>"
        for i, column in enumerate(value_columns)
    )
    rows = [f"<div style='margin:4px 0 10px'>{legend}</div>"]
    for _, row in frame.iterrows():
        bars = []
        for index, column in enumerate(value_columns):
            value = float(pd.to_numeric(row[column], errors="coerce") or 0)
            width = max(1.0, value / maximum * 100)
            bars.append(
                f"<div style='background:{colors[index]};height:12px;width:{width:.1f}%;margin:2px 0;border-radius:3px' title='{html.escape(column)}: {value:.1f}'></div>"
            )
        rows.append(
            f"<div style='display:grid;grid-template-columns:160px 1fr;gap:8px;align-items:center'><span>{html.escape(str(row[label_column]))}</span><div>{''.join(bars)}</div></div>"
        )
    st.markdown("".join(rows), unsafe_allow_html=True)


def _render_history(conversation_id: str) -> None:
    for message in store.messages(conversation_id, role=role):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("route"):
                _render_public_reasoning(
                    message["route"],
                    message.get("reasoning"),
                    key=f"history-{message['id']}",
                )
            if message.get("sources"):
                _render_sources(message["sources"])
            if message["role"] == "assistant":
                if st.button("🔊", key=f"speak-history-{message['id']}"):
                    _speak(message["content"])
                _render_feedback(message)


SUGGESTED_PROMPTS = (
    (
        "Políticas e documentos",
        "Qual é a carga horária de um cargo sênior?",
        "prompt-policy-hours",
    ),
    (
        "Políticas e documentos",
        "Quais competências são obrigatórias para um Analista de Dados Júnior?",
        "prompt-policy-skills",
    ),
    ("Indicadores e dados", "Quais competências têm mais lacunas?", "prompt-data-gaps"),
    (
        "Indicadores e dados",
        "Quais treinamentos estão disponíveis?",
        "prompt-data-training",
    ),
    (
        "Competências e trilhas",
        "Qual trilha de desenvolvimento combina com este colaborador?",
        "prompt-ml-track",
    ),
    (
        "Currículo em PDF",
        "Analise este currículo para desenvolvimento profissional.",
        "prompt-resume-analysis",
    ),
)


def _select_suggested_prompt(prompt: str) -> None:
    st.session_state.pending_prompt = prompt
    st.rerun()


def _render_sidebar(
    database: SkillGraphDatabase | None, db_error: str | None, role: str
) -> None:
    technical = role == UserRole.DESENVOLVEDOR.value
    with st.sidebar:
        st.subheader("Sobre o protótipo")
        st.write(
            "Assistente de competências e aprendizagem corporativa. Os dados da NexaTech são sintéticos."
        )
        if technical:
            st.caption("Backend técnico: Dify + Weaviate gerenciado")
            if db_error:
                st.warning(f"DuckDB indisponível: {db_error}")
            else:
                st.success("DuckDB: camada de dados disponível")
            if (
                st.button(
                    "Testar indicador de lacunas",
                    use_container_width=True,
                    key="developer-test-gaps",
                )
                and database
            ):
                st.dataframe(database.competency_gaps(), hide_index=True)
        st.divider()
        st.subheader("Conversas")
        if st.button(
            "＋  Nova conversa",
            type="primary",
            use_container_width=True,
            key="new-conversation-primary",
        ):
            st.session_state.active_conversation_id = store.create_conversation(
                "Nova conversa", "dify", role=role
            )
            st.session_state.conversation_id = ""
            st.rerun()
        conversation_search = st.text_input(
            "Buscar conversas",
            key="conversation-search",
            placeholder="Título ou conteúdo...",
            label_visibility="collapsed",
        )
        conversations = (
            store.search_conversations(conversation_search, role=role)
            if conversation_search.strip()
            else store.list_conversations(role=role)
        )
        if conversation_search.strip():
            st.caption(f"{len(conversations)} conversa(s) encontrada(s)")
            if not conversations:
                st.info("Nenhuma conversa corresponde à busca.")
        for conversation in conversations:
            _migrate_conversation_title(conversation)
            if st.button(
                conversation["title"] or "Nova conversa",
                key=f"conversation-{conversation['id']}",
                use_container_width=True,
            ):
                st.session_state.active_conversation_id = conversation["id"]
                st.session_state.conversation_id = conversation.get(
                    "dify_conversation_id", ""
                )
                st.rerun()
        st.divider()
        st.markdown("### Experimente perguntar")
        st.caption(
            "Clique em uma sugestão para preencher o campo de mensagem. O envio continua sob seu controle."
        )
        current_category = None
        for category, prompt, key in SUGGESTED_PROMPTS:
            if category != current_category:
                st.markdown(f"**{category}**")
                current_category = category
            help_text = (
                "Anexe o PDF no chat antes de enviar."
                if category == "Currículo em PDF"
                else None
            )
            if st.button(prompt, key=key, use_container_width=True, help=help_text):
                _select_suggested_prompt(prompt)
        st.caption("As sugestões usam dados sintéticos da NexaTech.")
        current_id = st.session_state.get("active_conversation_id")
        if st.button(
            "Apagar conversa atual", use_container_width=True, disabled=not current_id
        ):
            store.delete_conversation(current_id, role=role)
            st.session_state.active_conversation_id = None
            st.session_state.conversation_id = ""
            st.rerun()


st.set_page_config(page_title="SkillGraph", page_icon="🤖", layout="centered")
st.markdown(
    """<style>.st-key-new-conversation-primary button{background-color:#16A34A!important;border-color:#16A34A!important;color:#fff!important;font-weight:700!important}.st-key-new-conversation-primary button:hover{background-color:#15803D!important;border-color:#15803D!important}</style>""",
    unsafe_allow_html=True,
)
st.title("SkillGraph")
st.caption("Assistente de competências e aprendizagem corporativa — NexaTech")
DATA_DIR = PROJECT_ROOT / "data_bd"
try:
    database = SkillGraphDatabase(DATA_DIR)
    db_error = None
except SQLToolError as exc:
    database, db_error = None, str(exc)

with st.sidebar:
    role = st.selectbox(
        "Perfil simulado",
        [UserRole.DESENVOLVEDOR.value, UserRole.GESTOR.value, UserRole.RH.value],
        help="Perfis são simulados no MVP; não substituem autenticação real.",
    )
    st.session_state.selected_role = role
    if role == UserRole.GESTOR.value:
        gestor_view = st.radio(
            "Área",
            ["Chat SkillGraph", "Visão do gestor", "Machine Learning"],
            horizontal=True,
            key="gestor-area",
        )
    elif role == UserRole.DESENVOLVEDOR.value:
        gestor_view = st.radio(
            "Área",
            [
                "Chat SkillGraph",
                "Machine Learning",
                "Observabilidade",
                "Qualidade e Evals",
            ],
            horizontal=True,
            key="developer-area",
        )
    else:
        gestor_view = st.radio(
            "Área",
            ["Chat SkillGraph", "Machine Learning"],
            horizontal=True,
            key="general-area",
        )
    _render_sidebar(database, db_error, role)

if "active_conversation_id" not in st.session_state:
    st.session_state.active_conversation_id = None
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = ""

role_conversations = store.list_conversations(role=role)
if st.session_state.active_conversation_id not in {
    item["id"] for item in role_conversations
}:
    st.session_state.active_conversation_id = (
        role_conversations[0]["id"] if role_conversations else None
    )
    active = (
        store.get_conversation(st.session_state.active_conversation_id, role=role)
        if st.session_state.active_conversation_id
        else None
    )
    st.session_state.conversation_id = (
        active.get("dify_conversation_id", "") if active else ""
    )

if gestor_view == "Machine Learning":
    _render_ml_page()
    st.stop()

if role == UserRole.DESENVOLVEDOR.value and gestor_view == "Observabilidade":
    from src.observability_ui import render_observability

    render_observability()
    st.stop()

if role == UserRole.DESENVOLVEDOR.value and gestor_view == "Qualidade e Evals":
    from src.quality_ui import render_quality

    render_quality()
    st.stop()

if role == UserRole.GESTOR.value and gestor_view == "Visão do gestor":
    st.header("Visão do gestor")
    st.caption(
        "Indicadores agregados para apoiar conversas de desenvolvimento. Os dados são sintéticos."
    )
    if database:
        options = database.manager_filter_options()
        st.subheader("Filtros")
        filter_columns = st.columns(3)
        selected_category = filter_columns[0].selectbox(
            "Categoria",
            ["Todas"] + options["categorias"],
            key="manager-filter-category",
        )
        selected_competency = filter_columns[1].selectbox(
            "Competência",
            ["Todas"] + options["competencias"],
            key="manager-filter-competency",
        )
        selected_modality = filter_columns[2].selectbox(
            "Modalidade",
            ["Todas"] + options["modalidades"],
            key="manager-filter-modality",
        )
        if (
            selected_category != "Todas"
            or selected_competency != "Todas"
            or selected_modality != "Todas"
        ):
            st.caption(
                f"Filtros ativos: {selected_category} · {selected_competency} · {selected_modality}"
            )
        with st.expander("Como interpretar os indicadores", expanded=False):
            st.markdown(
                "- **Competências avaliadas:** competências distintas com registros de avaliação.\n"
                "- **Funcionários com lacuna:** pessoas distintas com ao menos um déficit agregado.\n"
                "- **Lacuna crítica:** registro marcado como risco crítico nos dados sintéticos.\n"
                "- **Lacuna comum:** déficit abaixo do obrigatório sem marcação crítica.\n"
                "- **Taxa de aprovação:** registros aprovados divididos pelo total de registros.\n"
                "- **Nota média:** média das notas registradas.\n"
                "- **Horas associadas:** duração de catálogo associada aos registros, não horas comprovadamente realizadas.\n"
                "- **Custo associado:** referência sintética de catálogo, não despesa financeira individual."
            )
        category_filter = None if selected_category == "Todas" else selected_category
        competency_filter = (
            None if selected_competency == "Todas" else selected_competency
        )
        modality_filter = None if selected_modality == "Todas" else selected_modality
        kpis = database.manager_kpis()
        st.subheader("Resumo executivo")
        kpi_columns = st.columns(5)
        kpi_columns[0].metric(
            "Competências avaliadas",
            kpis["competencias_avaliadas"],
            help="Quantidade distinta de competências com registros de avaliação.",
        )
        kpi_columns[1].metric(
            "Funcionários com lacuna",
            kpis["funcionarios_com_lacuna"],
            help="Quantidade agregada de funcionários com pelo menos uma competência abaixo do nível obrigatório.",
        )
        kpi_columns[2].metric(
            "Lacunas críticas",
            kpis["lacunas_criticas"],
            help="Registros marcados como risco de lacuna crítica.",
        )
        kpi_columns[3].metric(
            "Taxa de aprovação",
            f"{kpis['taxa_aprovacao']:.1f}%",
            help="Percentual agregado de treinamentos registrados como aprovados.",
        )
        kpi_columns[4].metric(
            "Nota média",
            f"{kpis['nota_media']:.1f}",
            help="Média agregada das notas dos treinamentos registrados.",
        )
        st.caption(
            f"Horas no catálogo: **{kpis['horas_catalogo']}h**. Dados sintéticos e agregados; não representam avaliação individual nem decisão de carreira."
        )
        gaps = pd.DataFrame(
            database.competency_gap_breakdown(
                limit=10, category=category_filter, competency=competency_filter
            )
        )
        if not gaps.empty:
            total_critical = int(gaps["lacunas_criticas"].sum())
            total_common = int(gaps["lacunas_comuns"].sum())
            gap_cards = st.columns(2)
            gap_cards[0].metric(
                "Lacunas críticas",
                total_critical,
                help="Déficits explicitamente marcados como risco crítico nos dados sintéticos.",
            )
            gap_cards[1].metric(
                "Lacunas comuns",
                total_common,
                help="Déficits abaixo do nível obrigatório sem marcação de risco crítico.",
            )
            st.subheader("Lacunas por competência")
            gap_table = gaps.rename(
                columns={
                    "competencia": "Competência",
                    "funcionarios_com_deficit": "Pessoas com déficit",
                    "lacunas_criticas": "Lacunas críticas",
                    "lacunas_comuns": "Lacunas comuns",
                    "percentual_critico": "% crítica",
                }
            )
            st.dataframe(gap_table, hide_index=True, use_container_width=True)
            chart_data = gaps.rename(columns={"competencia": "Competência"})
            _render_grouped_manager_chart(
                chart_data, "Competência", ["lacunas_criticas", "lacunas_comuns"]
            )
            st.caption(
                "Gráfico: barras vermelhas representam lacunas críticas; barras azuis representam lacunas comuns."
            )
            st.caption(
                "**Lacuna crítica** = registro marcado como risco crítico. "
                "**Lacuna comum** = déficit abaixo do nível obrigatório sem essa marcação. "
                "Dados sintéticos e agregados."
            )
        training_kpis = database.training_kpis_filtered(
            modality=modality_filter, category=category_filter
        )
        st.subheader("Indicadores de treinamentos")
        training_cards = st.columns(5)
        training_cards[0].metric(
            "Registros",
            training_kpis["registros"],
            help="Quantidade agregada de registros de treinamentos.",
        )
        training_cards[1].metric(
            "Taxa de aprovação",
            f"{training_kpis['taxa_aprovacao']:.1f}%",
            help="Percentual agregado de registros aprovados.",
        )
        training_cards[2].metric(
            "Nota média",
            f"{training_kpis['nota_media']:.1f}",
            help="Média agregada das notas registradas.",
        )
        training_cards[3].metric(
            "Horas associadas",
            f"{training_kpis['horas_associadas']}h",
            help="Duração de catálogo associada aos registros de treinamento.",
        )
        training_cards[4].metric(
            "Reprovações",
            training_kpis["reprovacoes"],
            help="Quantidade agregada de registros não aprovados.",
        )
        st.caption(
            f"Custo de catálogo associado: **R$ {training_kpis['custo_catalogo_associado']:,.2f}**. É uma referência sintética de catálogo, não uma despesa financeira individual."
        )
        completion = pd.DataFrame(
            database.training_completion_breakdown(
                modality=modality_filter, category=category_filter
            )
        )
        if not completion.empty:
            st.subheader("Aprovados versus reprovados")
            st.dataframe(
                completion.rename(
                    columns={
                        "status": "Status",
                        "registros": "Registros",
                        "nota_media": "Nota média",
                    }
                ),
                hide_index=True,
                use_container_width=True,
            )
            _render_manager_chart(
                completion.rename(columns={"status": "Status"}),
                value_column="registros",
            )
            st.caption(
                "Dados agregados de aprovação em treinamentos; não representam desempenho individual."
            )
        training = pd.DataFrame(
            database.training_summary_filtered(
                modality=modality_filter, category=category_filter, limit=20
            )
        )
        if not training.empty:
            st.subheader("Desenvolvimento e treinamentos")
            st.dataframe(training, hide_index=True, use_container_width=True)
            _render_manager_chart(training, value_column="treinamentos")
            st.caption(
                "Gráfico: quantidade de treinamentos por modalidade no filtro selecionado."
            )
        st.subheader("Evolução temporal agregada")
        temporal_training = pd.DataFrame(
            database.training_temporal_summary(
                modality=modality_filter, category=category_filter
            )
        )
        if not temporal_training.empty:
            st.markdown("**Registros de treinamentos por mês**")
            st.line_chart(
                temporal_training.set_index("mes")[["aprovados", "reprovados"]]
            )
        else:
            st.info(
                "Não há registros temporais de treinamentos para os filtros selecionados."
            )
        temporal_gaps = pd.DataFrame(
            database.competency_gap_temporal_summary(
                category=category_filter, competency=competency_filter
            )
        )
        if not temporal_gaps.empty:
            st.markdown("**Lacunas por mês de avaliação**")
            st.line_chart(
                temporal_gaps.set_index("mes")[["lacunas_criticas", "lacunas_comuns"]]
            )
        else:
            st.info(
                "Não há registros temporais de lacunas para os filtros selecionados."
            )
        st.caption(
            "A evolução representa a variação observada em registros agregados sintéticos; não indica causalidade nem desempenho individual."
        )
    st.info(
        "A visão é agregada e não exibe dados pessoais ou decisões automáticas de carreira."
    )
    st.stop()

if st.session_state.active_conversation_id:
    _render_history(st.session_state.active_conversation_id)
else:
    st.info(
        "Comece uma conversa sobre políticas, cargos, competências ou trilhas de desenvolvimento."
    )

if st.session_state.get("pending_resume_text"):
    st.info(
        f"Currículo recebido: {st.session_state.get('pending_resume_name', 'PDF')}. "
        "Clique em **Enviar análise** para iniciar o processamento.\n\n"
        "**A análise de currículo demora um pouco mais e pode levar até 5 minutos devido ao fluxo de OCR, JEV e agentes especializados.**"
    )
    if st.button("Enviar análise", key="send-resume-analysis", type="primary"):
        question = st.session_state.pop(
            "pending_resume_question",
            "Analise este currículo para desenvolvimento profissional.",
        )
        conversation_id = _ensure_resume_conversation(question, role)
        resume_text = st.session_state.pop("pending_resume_text")
        st.session_state.pop("pending_resume_name", None)
        request_id = str(uuid.uuid4())
        trace = TraceContext(route="resume_analysis", role=role, user_key=request_id)
        trace.__enter__()
        progress = ResumeProgress.start()
        try:
            progress.update(
                "ocr",
                "Texto do currículo extraído",
                "A extração local/OCR foi concluída.",
            )
            with trace.span("document.extract", "ocr", task_name="pdf_text_extraction"):
                pass
            progress.update(
                "jev",
                "Consultando análise estruturada",
                "Os sinais estruturados estão sendo processados.",
            )
            with trace.span("crewai.resume", "crewai", task_name="resume_analysis"):
                agent_result = run_agent_turn(
                    question, resume_text=resume_text, has_resume=True, trace=trace
                )
            progress.update(
                "agents",
                "Agentes especializados concluídos",
                "O perfil foi revisado e a resposta está sendo preparada.",
            )
            answer = agent_result.get("answer", "Análise multiagente concluída.")
            resume_profile = agent_result.get("profile")
            reasoning_steps = agent_result.get("reasoning", [])
            _render_resume_profile(resume_profile)
            _render_public_reasoning(
                "resume_analysis", reasoning_steps, key=f"resume-{request_id}"
            )
            conversation_id = st.session_state.get("active_conversation_id")
            if conversation_id:
                store.add_message(
                    conversation_id,
                    "user",
                    question,
                    route="resume_analysis",
                    request_id=request_id,
                    conversation_role=role,
                )
                assistant_id = store.add_message(
                    conversation_id,
                    "assistant",
                    answer,
                    route="resume_analysis",
                    request_id=request_id,
                    reasoning=reasoning_steps,
                    conversation_role=role,
                )
                _render_feedback(
                    {
                        "id": assistant_id,
                        "content": answer,
                        "route": "resume_analysis",
                        "trace_id": trace.trace_id,
                    }
                )
            st.chat_message("user").markdown(question)
            st.chat_message("assistant").markdown(answer)
            progress.finish(True)
            trace.finish("success")
            OBSERVABILITY.record(trace)
        except Exception as exc:
            progress.finish(False, "Verifique a configuração local ou tente novamente.")
            trace.finish("error", str(exc))
            OBSERVABILITY.record(trace)
            render_error_panel(
                trace_id=trace.trace_id,
                route="resume_analysis",
                started=progress.started,
                error=exc,
                developer=role == UserRole.DESENVOLVEDOR.value,
            )
        st.stop()

st.info(upload_privacy_notice())
pending_prompt = st.session_state.pop("pending_prompt", "")
if pending_prompt:
    st.info(f"Sugestão selecionada: **{pending_prompt}**. Pressione Enter para enviar.")
    st.session_state.pending_prompt_value = pending_prompt
chat_value = st.chat_input(
    "Faça uma pergunta sobre desenvolvimento profissional…",
    accept_file="multiple",
    file_type=["pdf"],
    max_chars=4000,
)
question_from_suggestion = st.session_state.pop("pending_prompt_value", "")
question = chat_value.text if hasattr(chat_value, "text") else chat_value
question = question or question_from_suggestion
uploaded_files = list(getattr(chat_value, "files", []) or []) if chat_value else []
if question or uploaded_files:
    if len(uploaded_files) > 1:
        st.error("Envie apenas um currículo PDF por análise.")
        st.stop()
    resume_text = None
    if uploaded_files:
        try:
            import tempfile

            uploaded = uploaded_files[0]
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as temporary:
                temporary.write(uploaded.getvalue())
                temporary.flush()
                resume_text = extract_pdf_text(Path(temporary.name)).text
            question = (
                question or "Analise este currículo para desenvolvimento profissional."
            )
            st.session_state["pending_resume_text"] = resume_text
            st.session_state["pending_resume_question"] = question
            st.session_state["pending_resume_name"] = uploaded.name
            st.rerun()
        except ResumeExtractionError as exc:
            st.error(str(exc))
            st.stop()
    if not question:
        st.stop()
    request_id = str(uuid.uuid4())
    trace = TraceContext(route="pending", role=role, user_key=request_id)
    trace.__enter__()
    if resume_text:
        with trace.span("document.extract", "ocr", task_name="pdf_text_extraction"):
            pass
        with trace.span("crewai.resume", "crewai", task_name="resume_analysis"):
            agent_result = run_agent_flow(
                question,
                resume_text=resume_text,
                has_resume=True,
                trace=trace,
            )
            if agent_result.get("status") == "completed":
                st.info(agent_result.get("answer", "Análise multiagente concluída."))
            else:
                st.warning(
                    agent_result.get("answer", "O fluxo multiagente está desativado.")
                )
        trace.route = "resume_analysis"
        trace.finish("success")
        OBSERVABILITY.record(trace)
        st.stop()
    started = time.perf_counter()
    decision = evaluate_input(question, UserRole(role))
    if not decision.allowed:
        answer = decision.public_message
        record_event(
            LOG_PATH,
            request_id=request_id,
            route="blocked",
            status="blocked",
            latency_ms=(time.perf_counter() - started) * 1000,
            blocked=True,
        )
        st.error(answer)
        trace.finish("blocked", "input_guardrail")
        OBSERVABILITY.record(trace)
        st.stop()

    if not st.session_state.active_conversation_id:
        st.session_state.active_conversation_id = store.create_conversation(
            _title_from_question(question), "dify", role=role
        )
    conversation_id = st.session_state.active_conversation_id
    route = route_question(question)
    agent_route = route_turn(question)
    use_agent_runtime = (
        os.getenv("CREWAI_ENABLED", "false").casefold() == "true"
        and agent_route.value in {"training_recommendation", "policy_rag"}
        and route.intent in {Intent.RAG, Intent.SQL_INDICATOR}
    )
    trace.route = agent_route.value if use_agent_runtime else route.intent.value
    store.add_message(
        conversation_id,
        "user",
        question,
        route=agent_route.value if use_agent_runtime else route.intent.value,
        request_id=request_id,
        conversation_role=role,
    )
    conversation_messages = store.messages(conversation_id, role=role)
    if (
        len(conversation_messages) == 1
        or store.get_conversation(conversation_id, role=role).get("title")
        == "Nova conversa"
    ):
        store.set_title(conversation_id, _title_from_question(question), role=role)

    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        progress = st.empty()
        progress.info("Analisando sua pergunta…")
        answer, sources, tools, table_rows, chart_frame = "", [], [], None, None
        agent_handled = False
        try:
            if use_agent_runtime:
                progress.info("Executando o fluxo multiagente…")
                agent_result = run_agent_turn(
                    question,
                    conversation_state=store.agent_state(
                        conversation_id, role=role
                    ),
                    trace=trace,
                )
                agent_status = agent_result.get("status")
                if agent_status == "completed":
                    answer = agent_result.get(
                        "answer", "O fluxo multiagente foi concluído."
                    )
                    reasoning_steps = agent_result.get("reasoning", [])
                    tools = [
                        "TrainingCatalogTool"
                        if agent_result.get("route") == "training_recommendation"
                        else "DifyPolicyTool"
                    ]
                    store.update_agent_state(
                        conversation_id,
                        {
                            **store.agent_state(conversation_id, role=role),
                            **agent_result.get("state_patch", {}),
                        },
                        role=role,
                    )
                    agent_handled = True
                elif agent_status in {"disabled", "error"}:
                    use_agent_runtime = False
                    trace.route = route.intent.value
                    progress.info(
                        "Fluxo multiagente indisponível; usando o fluxo compatível."
                    )
                elif agent_status in {"blocked", "clarify", "local"}:
                    answer = agent_result.get(
                        "answer", "O fluxo multiagente não foi concluído."
                    )
                    reasoning_steps = agent_result.get("reasoning", [])
                    tools = ["agent_guardrail"]
                    agent_handled = True
                else:
                    raise DifyClientError(
                        agent_result.get(
                            "answer", "O fluxo multiagente não foi concluído."
                        )
                    )

            if not agent_handled and route.intent is Intent.SMALLTALK:
                answer = answer_smalltalk_question(question).answer
                tools = ["smalltalk"]
            elif not agent_handled and route.intent is Intent.COMPARISON:
                progress.info("Comparando as informações…")
                result = answer_comparison_question(question)
                answer = result.answer
                table_rows = result.rows or []
                if table_rows:
                    frame = pd.DataFrame(table_rows)
                    chart_frame = frame.rename(
                        columns={
                            "nível": "categoria",
                            "carga mínima anual (horas)": "valor",
                        }
                    )
                tools = ["training_hours_comparison"]
            elif not agent_handled and route.intent is Intent.COMPETENCY_LOOKUP and database:
                progress.info("Consultando dados de competências…")
                result = answer_competency_question(question, database)
                answer = result.answer
                tools = ["sql:competency_case_lookup"]
            elif not agent_handled and route.intent is Intent.SQL_INDICATOR and database:
                progress.info("Consultando dados estruturados…")
                with trace.span(
                    "duckdb.structured",
                    "duckdb",
                    task_name="answer_structured_question",
                ):
                    result = answer_structured_question(question, database)
                answer = result.answer
                table_rows = result.rows or []
                tools = [
                    (
                        "sql:competency_gap_summary"
                        if "lacuna" in question.lower()
                        or "competência" in question.lower()
                        else "sql:training_catalog"
                    )
                ]
            elif not agent_handled and route.intent is Intent.RAG:
                progress.info("Consultando documentos e preparando a resposta…")
                placeholder = st.empty()
                dify_id = st.session_state.conversation_id
                with trace.span("rag.dify", "dify", task_name="stream_chat"):
                    event_stream = stream_production_rag(
                        question, conversation_id=dify_id
                    )
                for event in event_stream:
                    if event.get("event") == "message":
                        answer += str(event.get("answer", ""))
                        dify_id = str(event.get("conversation_id") or dify_id)
                        placeholder.markdown(answer + "▌")
                    elif event.get("event") == "message_end":
                        sources.extend(_sources_from_event(event))
                if not answer:
                    raise DifyClientError(
                        "O Chatflow do Dify encerrou sem retornar uma resposta."
                    )
                st.session_state.conversation_id = dify_id
                placeholder.empty()
                tools = ["rag:dify"]
            elif not agent_handled:
                raise DifyClientError(
                    "Não foi possível encaminhar essa pergunta com segurança."
                )
            progress.empty()
        except (DifyClientError, SQLToolError) as exc:
            progress.empty()
            st.error(
                "Não consegui concluir esta solicitação. Tente novamente ou reformule a pergunta. "
                f"Detalhe: {exc}"
            )
            trace.finish("error", str(exc))
            OBSERVABILITY.record(trace)
            record_event(
                LOG_PATH,
                request_id=request_id,
                route=agent_route.value if use_agent_runtime else route.intent.value,
                status="error",
                latency_ms=(time.perf_counter() - started) * 1000,
                error=True,
            )
            st.stop()

        if not use_agent_runtime:
            reasoning_steps = route_steps(route.intent.value)
        _render_public_reasoning(
            agent_route.value if use_agent_runtime else route.intent.value,
            reasoning_steps,
            key=f"live-{request_id}",
        )
        answer, toxicity = safe_response(answer)
        st.markdown(answer)
        if table_rows:
            st.dataframe(table_rows, hide_index=True, use_container_width=True)
        if chart_frame is not None:
            _render_manager_chart(chart_frame)
        _render_sources(sources)
        assistant_id = store.add_message(
            conversation_id,
            "assistant",
            answer,
            route=agent_route.value if use_agent_runtime else route.intent.value,
            request_id=request_id,
            sources=sources,
            reasoning=reasoning_steps,
            conversation_role=role,
        )
        _render_feedback(
            {
                "id": assistant_id,
                "content": answer,
                "route": agent_route.value if use_agent_runtime else route.intent.value,
                "trace_id": trace.trace_id,
            }
        )
        trace.finish("success")
        OBSERVABILITY.record(trace)
        if st.button("🔊 Ouvir resposta", key=f"speak-live-{assistant_id}"):
            _speak(answer)
        record_event(
            LOG_PATH,
            request_id=request_id,
            route=agent_route.value if use_agent_runtime else route.intent.value,
            status="success",
            latency_ms=(time.perf_counter() - started) * 1000,
            tools=tools,
            sources_count=len(sources),
        )
