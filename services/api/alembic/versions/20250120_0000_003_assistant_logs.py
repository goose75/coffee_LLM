"""Add assistant_logs table

Revision ID: 003_assistant_logs
Revises: 002_flavour_taxonomy
Create Date: 2025-01-20 00:00:00

Stores every assistant interaction for:
  - Hallucination risk flagging
  - Intent distribution analytics
  - Failure investigation
  - Prompt regression testing

Design notes:
  - Append-only (no UPDATE/DELETE rules like price_history)
  - retrieved_context stores the DB records injected into the prompt
  - hallucination_risk is a heuristic score 0-1 computed post-response
  - flagged allows manual admin marking
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003_assistant_logs"
down_revision = "002_flavour_taxonomy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # Session tracking (no auth required — anonymous UUID from client)
        sa.Column("session_id", sa.String(64), nullable=False, index=True),
        # The raw user message
        sa.Column("user_message", sa.Text, nullable=False),
        # Classified intent (search, compare, recommend, brew_advice, price, general)
        sa.Column("intent", sa.String(50), nullable=True),
        # Which retrieval tools were called and their params
        sa.Column("retrieval_calls", postgresql.JSONB, nullable=False, server_default="'[]'"),
        # The DB records injected as context (truncated to token budget)
        sa.Column("retrieved_context", postgresql.JSONB, nullable=False, server_default="'[]'"),
        # Token counts for cost tracking
        sa.Column("prompt_tokens", sa.Integer, nullable=True),
        sa.Column("completion_tokens", sa.Integer, nullable=True),
        # The assistant's final response text
        sa.Column("assistant_response", sa.Text, nullable=True),
        # 0.0-1.0 heuristic: did response cite records? mention prices not in context?
        sa.Column("hallucination_risk", sa.Float, nullable=True),
        # True if the retrieval returned 0 records but the model still answered
        sa.Column("answered_without_grounding", sa.Boolean, nullable=False, server_default="false"),
        # Error information if the request failed
        sa.Column("error", sa.Text, nullable=True),
        # Duration for latency tracking
        sa.Column("duration_ms", sa.Integer, nullable=True),
        # Manual admin flag
        sa.Column("flagged", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("flag_reason", sa.String(500), nullable=True),
        # Prompt version for regression tracking
        sa.Column("prompt_version", sa.String(50), nullable=False, server_default="'assistant-v1.0.0'"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            index=True,
        ),
    )

    # Indexes for the admin observability queries
    op.create_index("ix_assistant_logs_intent", "assistant_logs", ["intent"])
    op.create_index("ix_assistant_logs_hallucination_risk", "assistant_logs", ["hallucination_risk"])
    op.create_index("ix_assistant_logs_flagged", "assistant_logs", ["flagged"])
    op.create_index("ix_assistant_logs_answered_without_grounding",
                    "assistant_logs", ["answered_without_grounding"])

    # Append-only protection
    op.execute("""
        CREATE RULE assistant_logs_no_update AS
        ON UPDATE TO assistant_logs DO INSTEAD NOTHING;
    """)
    op.execute("""
        CREATE RULE assistant_logs_no_delete AS
        ON DELETE TO assistant_logs DO INSTEAD NOTHING;
    """)


def downgrade() -> None:
    op.drop_table("assistant_logs")
