"""move properties.image_urls into property_media

Revision ID: 8b3d6f2e1a45
Revises: 5e1f0c8a7b62
Create Date: 2026-09-29 15:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8b3d6f2e1a45"
down_revision: str | Sequence[str] | None = "5e1f0c8a7b62"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Each URL becomes a public IMAGE row, keeping its position in the list as sort order
    op.execute(
        """
        INSERT INTO property_media (property_id, kind, s3_key, content_type, sort_order, is_public)
        SELECT p.id, 'IMAGE', u.url, 'image/jpeg', (u.pos - 1)::int, true
        FROM properties p
        CROSS JOIN LATERAL jsonb_array_elements_text(p.image_urls) WITH ORDINALITY AS u(url, pos)
        """
    )
    op.drop_column("properties", "image_urls")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "properties",
        sa.Column(
            "image_urls",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.execute(
        """
        UPDATE properties p
        SET image_urls = m.urls
        FROM (
            SELECT property_id, jsonb_agg(s3_key ORDER BY sort_order, id) AS urls
            FROM property_media
            WHERE kind = 'IMAGE' AND is_public
            GROUP BY property_id
        ) m
        WHERE m.property_id = p.id
        """
    )
    op.execute("DELETE FROM property_media WHERE kind = 'IMAGE'")
    op.alter_column("properties", "image_urls", server_default=None)
