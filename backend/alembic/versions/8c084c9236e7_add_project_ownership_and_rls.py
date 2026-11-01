"""add_project_ownership_and_rls

Revision ID: 8c084c9236e7
Revises: 6778f03ff323
Create Date: 2026-11-01 11:19:33.007926

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c084c9236e7'
down_revision: Union[str, Sequence[str], None] = '6778f03ff323'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema with project ownership, visibility, soft delete, and RLS."""
    # 1. Add columns to projects table
    op.add_column('projects', sa.Column('owner_id', sa.Uuid(), nullable=True))
    op.add_column('projects', sa.Column('owner_type', sa.String(length=20), server_default='individual', nullable=True))
    op.add_column('projects', sa.Column('creator_id', sa.Uuid(), nullable=True))
    op.add_column('projects', sa.Column('visibility', sa.String(length=20), server_default='private', nullable=False))
    op.add_column('projects', sa.Column('unlisted_token', sa.String(length=64), nullable=True))
    op.add_column('projects', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('projects', sa.Column('deleted_by', sa.Uuid(), nullable=True))
    op.add_column('projects', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True))

    # 2. Add indices
    op.create_index('ix_projects_owner_id', 'projects', ['owner_id'])
    op.create_index('ix_projects_creator_id', 'projects', ['creator_id'])
    op.create_index('ix_projects_visibility', 'projects', ['visibility'])
    op.create_index('ix_projects_unlisted_token', 'projects', ['unlisted_token'], unique=True)
    op.create_index('ix_projects_deleted_at', 'projects', ['deleted_at'])

    # 3. Ensure Row-Level Security is enabled
    op.execute("ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;")

    # 4. Grant DML and sequence permissions to restricted runtime role hackpreneur_app
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON public.projects TO hackpreneur_app;")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO hackpreneur_app;")

    # 5. Define Row-Level Security Policies for hackpreneur_app
    op.execute("""
    CREATE POLICY projects_select_policy ON public.projects
    FOR SELECT
    TO hackpreneur_app
    USING (
        (
            deleted_at IS NULL
            AND (
                (visibility = 'public' AND NULLIF(current_setting('app.current_user_id', true), '') IS NOT NULL)
                OR (owner_id IS NOT NULL AND owner_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid)
                OR (creator_id IS NOT NULL AND creator_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid)
                OR (visibility = 'unlisted' AND unlisted_token IS NOT NULL AND unlisted_token = NULLIF(current_setting('app.unlisted_token', true), ''))
            )
        )
        OR (
            owner_id IS NOT NULL
            AND owner_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
        )
    );
    """)

    op.execute("""
    CREATE POLICY projects_insert_policy ON public.projects
    FOR INSERT
    TO hackpreneur_app
    WITH CHECK (
        NULLIF(current_setting('app.current_user_id', true), '') IS NOT NULL
        AND creator_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
        AND (owner_id IS NULL OR owner_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid)
    );
    """)

    op.execute("""
    CREATE POLICY projects_update_policy ON public.projects
    FOR UPDATE
    TO hackpreneur_app
    USING (
        owner_id IS NOT NULL
        AND owner_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
    )
    WITH CHECK (
        owner_id IS NOT NULL
        AND owner_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
    );
    """)

    op.execute("""
    CREATE POLICY projects_delete_policy ON public.projects
    FOR DELETE
    TO hackpreneur_app
    USING (
        owner_id IS NOT NULL
        AND owner_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
    );
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP POLICY IF EXISTS projects_delete_policy ON public.projects;")
    op.execute("DROP POLICY IF EXISTS projects_update_policy ON public.projects;")
    op.execute("DROP POLICY IF EXISTS projects_insert_policy ON public.projects;")
    op.execute("DROP POLICY IF EXISTS projects_select_policy ON public.projects;")

    op.drop_index('ix_projects_deleted_at', table_name='projects')
    op.drop_index('ix_projects_unlisted_token', table_name='projects')
    op.drop_index('ix_projects_visibility', table_name='projects')
    op.drop_index('ix_projects_creator_id', table_name='projects')
    op.drop_index('ix_projects_owner_id', table_name='projects')

    op.drop_column('projects', 'updated_at')
    op.drop_column('projects', 'deleted_by')
    op.drop_column('projects', 'deleted_at')
    op.drop_column('projects', 'unlisted_token')
    op.drop_column('projects', 'visibility')
    op.drop_column('projects', 'creator_id')
    op.drop_column('projects', 'owner_type')
    op.drop_column('projects', 'owner_id')
