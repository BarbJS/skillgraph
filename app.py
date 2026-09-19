"""Streamlit interface for the SkillGraph Etapa 1 MVP."""

from __future__ import annotations

import html
import os
import time
import uuid
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

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
from src.monitoring import METRICS, record_event
from src.security import UserRole, evaluate_input
from src.session_store import SessionStore
from src.sql_tools import SQLToolError, SkillGraphDatabase

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
                item.get("document_name")
                or item.get("title")
                or item.get("name")
                or ""
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
        (("carga horária", "carga horaria", "horas de treinamento"), "Comparação de carga horária entre cargos"),
        (("competências", "competencias", "lacunas"), "Indicadores de lacunas de competências"),
        (("treinamentos", "treinamento", "cursos"), "Catálogo e recomendações de treinamentos"),
        (("trilha", "trilhas", "desenvolvimento"), "Trilhas de desenvolvimento profissional"),
        (("política", "politica", "elegibilidade", "reembolso"), "Políticas de treinamento"),
        (("cargo", "cargos", "requisitos", "senioridade"), "Requisitos e competências de cargos"),
        (("risco de lacuna", "diagnóstico"), "Consulta de diagnóstico de competências"),
    )
    for keywords, title in patterns:
        if any(keyword in normalized for keyword in keywords):
            return title
    return "Consulta sobre desenvolvimento profissional"


def _migrate_conversation_title(conversation: dict[str, Any]) -> None:
    """Replace legacy copied-question titles with concise topic labels."""

    title = conversation.get("title", "")
    if title and title != "Nova conversa" and not title.endswith("…"):
        return
    messages = store.messages(conversation["id"], role=role)
    first_user = next((item["content"] for item in messages if item["role"] == "user"), None)
    if first_user:
        new_title = _title_from_question(first_user)
        if new_title != title:
            store.rename_conversation(conversation["id"], new_title, role=role)


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
    if cols[1].button("👎", key=f"negative-{message_id}", help="Resposta precisa melhorar"):
        st.session_state[f"feedback_pending_{message_id}"] = -1
        st.rerun()

    pending = st.session_state.get(f"feedback_pending_{message_id}")
    if pending:
        comment = st.text_input("Comentário opcional", key=f"feedback-comment-{message_id}")
        if st.button("Enviar feedback", key=f"feedback-submit-{message_id}"):
            feedback_store.save(
                message_id,
                pending,
                route=message.get("route", ""),
                comment=comment,
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


def _render_manager_chart(frame: pd.DataFrame) -> None:
    """Render a chart without Streamlit's Altair-dependent chart helper."""

    numeric = [column for column in frame.columns if pd.api.types.is_numeric_dtype(frame[column])]
    if not numeric or frame.empty:
        return
    chart_frame = frame.set_index(frame.columns[0])[[numeric[0]]].copy()
    chart_frame.columns = ["valor"]
    chart_frame["valor"] = pd.to_numeric(chart_frame["valor"], errors="coerce").fillna(0)
    maximum = max(float(chart_frame["valor"].max()), 1.0)
    bars = []
    for label, value in chart_frame["valor"].items():
        width = max(2.0, float(value) / maximum * 100)
        bars.append(
            "<div style='display:flex;align-items:center;gap:8px;margin:6px 0'>"
            f"<span style='width:140px;overflow:hidden;text-overflow:ellipsis'>"
            f"{html.escape(str(label))}</span>"
            f"<div style='background:#16A34A;height:18px;width:{width:.1f}%;border-radius:4px'></div>"
            f"<strong>{float(value):.0f}</strong></div>"
        )
    st.markdown("".join(bars), unsafe_allow_html=True)


def _render_history(conversation_id: str) -> None:
    for message in store.messages(conversation_id, role=role):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("sources"):
                _render_sources(message["sources"])
            if message["role"] == "assistant":
                if st.button("🔊", key=f"speak-history-{message['id']}"):
                    _speak(message["content"])
                _render_feedback(message)


def _render_sidebar(
    database: SkillGraphDatabase | None, db_error: str | None, role: str
) -> None:
    technical = role == UserRole.DESENVOLVEDOR.value
    with st.sidebar:
        st.subheader("Sobre o protótipo")
        st.write("Assistente de competências e aprendizagem corporativa. Os dados da NexaTech são sintéticos.")
        if technical:
            st.caption("Backend técnico: Dify + Weaviate gerenciado")
            if db_error:
                st.warning(f"DuckDB indisponível: {db_error}")
            else:
                st.success("DuckDB: camada de dados disponível")
            if st.checkbox("Mostrar observabilidade", key="developer-observability"):
                st.subheader("Métricas locais")
                st.json(METRICS.snapshot())
                st.caption("Métricas agregadas; nenhuma pergunta ou chave é exibida.")
            if st.button("Testar indicador de lacunas", use_container_width=True, key="developer-test-gaps") and database:
                st.dataframe(database.competency_gaps(), hide_index=True)
        st.divider()
        st.subheader("Conversas")
        if st.button("＋  Nova conversa", type="primary", use_container_width=True, key="new-conversation-primary"):
            st.session_state.active_conversation_id = store.create_conversation("Nova conversa", "dify", role=role)
            st.session_state.conversation_id = ""
            st.rerun()
        conversations = store.list_conversations(role=role)
        for conversation in conversations:
            _migrate_conversation_title(conversation)
            if st.button(conversation["title"] or "Nova conversa", key=f"conversation-{conversation['id']}", use_container_width=True):
                st.session_state.active_conversation_id = conversation["id"]
                st.session_state.conversation_id = conversation.get("dify_conversation_id", "")
                st.rerun()
        st.divider()
        st.markdown("### Experimente perguntar")
        st.caption("Escolha uma sugestão ou escreva sua própria pergunta.")
        st.markdown("**Políticas e documentos**")
        st.caption("• Qual é a carga horária de um cargo sênior?")
        st.markdown("**Indicadores e dados**")
        st.caption("• Quais competências têm mais lacunas?")
        st.caption("• Quais treinamentos estão disponíveis?")
        st.markdown("*As sugestões usam dados sintéticos da NexaTech.*")
        current_id = st.session_state.get("active_conversation_id")
        if st.button("Apagar conversa atual", use_container_width=True, disabled=not current_id):
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
            "Área", ["Chat SkillGraph", "Visão do gestor"], horizontal=True, key="gestor-area"
        )
    else:
        gestor_view = "Chat SkillGraph"
    _render_sidebar(database, db_error, role)

if "active_conversation_id" not in st.session_state:
    st.session_state.active_conversation_id = None
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = ""

role_conversations = store.list_conversations(role=role)
if st.session_state.active_conversation_id not in {item["id"] for item in role_conversations}:
    st.session_state.active_conversation_id = role_conversations[0]["id"] if role_conversations else None
    active = (
        store.get_conversation(st.session_state.active_conversation_id, role=role)
        if st.session_state.active_conversation_id
        else None
    )
    st.session_state.conversation_id = active.get("dify_conversation_id", "") if active else ""

if role == UserRole.GESTOR.value and gestor_view == "Visão do gestor":
    st.header("Visão do gestor")
    st.caption("Indicadores agregados para apoiar conversas de desenvolvimento. Os dados são sintéticos.")
    if database:
        gaps = pd.DataFrame(database.competency_gaps(limit=10))
        if not gaps.empty:
            st.subheader("Lacunas por competência")
            st.dataframe(gaps, hide_index=True, use_container_width=True)
            _render_manager_chart(gaps)
        training = pd.DataFrame(database.training_summary(limit=20))
        if not training.empty:
            st.subheader("Desenvolvimento e treinamentos")
            st.dataframe(training, hide_index=True, use_container_width=True)
            _render_manager_chart(training)
    st.info("A visão é agregada e não exibe dados pessoais ou decisões automáticas de carreira.")
    st.stop()

if st.session_state.active_conversation_id:
    _render_history(st.session_state.active_conversation_id)
else:
    st.info("Comece uma conversa sobre políticas, cargos, competências ou trilhas de desenvolvimento.")

question = st.chat_input("Faça uma pergunta sobre desenvolvimento profissional…")
if question:
    request_id = str(uuid.uuid4())
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
        st.stop()

    if not st.session_state.active_conversation_id:
        st.session_state.active_conversation_id = store.create_conversation(
            _title_from_question(question), "dify", role=role
        )
    conversation_id = st.session_state.active_conversation_id
    route = route_question(question)
    store.add_message(
        conversation_id,
        "user",
        question,
        route=route.intent.value,
        request_id=request_id,
        conversation_role=role,
    )
    conversation_messages = store.messages(conversation_id, role=role)
    if len(conversation_messages) == 1 or store.get_conversation(conversation_id, role=role).get("title") == "Nova conversa":
        store.set_title(conversation_id, _title_from_question(question), role=role)

    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        progress = st.empty()
        progress.info("Analisando sua pergunta…")
        answer, sources, tools, table_rows, chart_frame = "", [], [], None, None
        try:
            if route.intent is Intent.SMALLTALK:
                answer = answer_smalltalk_question(question).answer
                tools = ["smalltalk"]
            elif route.intent is Intent.COMPARISON:
                progress.info("Comparando as informações…")
                result = answer_comparison_question(question)
                answer = result.answer
                table_rows = result.rows or []
                if table_rows:
                    frame = pd.DataFrame(table_rows)
                    chart_frame = frame.rename(columns={"nível": "categoria", "carga mínima anual (horas)": "valor"})
                tools = ["training_hours_comparison"]
            elif route.intent is Intent.COMPETENCY_LOOKUP and database:
                progress.info("Consultando dados de competências…")
                result = answer_competency_question(question, database)
                answer = result.answer
                tools = ["sql:competency_case_lookup"]
            elif route.intent is Intent.SQL_INDICATOR and database:
                progress.info("Consultando dados estruturados…")
                result = answer_structured_question(question, database)
                answer = result.answer
                table_rows = result.rows or []
                tools = [
                    "sql:competency_gap_summary"
                    if "lacuna" in question.lower() or "competência" in question.lower()
                    else "sql:training_catalog"
                ]
            elif route.intent is Intent.RAG:
                progress.info("Consultando documentos e preparando a resposta…")
                placeholder = st.empty()
                dify_id = st.session_state.conversation_id
                for event in stream_production_rag(question, conversation_id=dify_id):
                    if event.get("event") == "message":
                        answer += str(event.get("answer", ""))
                        dify_id = str(event.get("conversation_id") or dify_id)
                        placeholder.markdown(answer + "▌")
                    elif event.get("event") == "message_end":
                        sources.extend(_sources_from_event(event))
                if not answer:
                    raise DifyClientError("O Chatflow do Dify encerrou sem retornar uma resposta.")
                st.session_state.conversation_id = dify_id
                tools = ["rag:dify"]
            else:
                raise DifyClientError("Não foi possível encaminhar essa pergunta com segurança.")
            progress.empty()
        except (DifyClientError, SQLToolError) as exc:
            progress.empty()
            st.error(
                "Não consegui concluir esta solicitação. Tente novamente ou reformule a pergunta. "
                f"Detalhe: {exc}"
            )
            record_event(
                LOG_PATH,
                request_id=request_id,
                route=route.intent.value,
                status="error",
                latency_ms=(time.perf_counter() - started) * 1000,
                error=True,
            )
            st.stop()

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
            route=route.intent.value,
            request_id=request_id,
            sources=sources,
            conversation_role=role,
        )
        _render_feedback({"id": assistant_id, "content": answer, "route": route.intent.value})
        if st.button("🔊 Ouvir resposta", key=f"speak-live-{assistant_id}"):
            _speak(answer)
        record_event(
            LOG_PATH,
            request_id=request_id,
            route=route.intent.value,
            status="success",
            latency_ms=(time.perf_counter() - started) * 1000,
            tools=tools,
            sources_count=len(sources),
        )
