# DocFormatConverter - 数据库设计文档

> **版本**: 1.0.0  
> **数据库**: PostgreSQL 16+  
> **ORM**: SQLAlchemy 2.0  
> **迁移**: Alembic

---

## 1. 数据库架构概览

### 1.1 实体关系图 (ERD)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Entity Relationship Diagram                        │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────┐       ┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│    users    │       │  api_keys   │       │    tasks    │       │   files     │
├─────────────┤       ├─────────────┤       ├─────────────┤       ├─────────────┤
│ id (PK)     │◀──────│ user_id(FK) │       │ id (PK)     │◀──────│ task_id(FK) │
│ email       │       │ id (PK)     │       │ user_id(FK) │       │ id (PK)     │
│ password_hash│       │ key_hash    │       │ batch_id    │──────▶│ batch_id(FK)│
│ name        │       │ name        │       │ status      │       │ storage_key │
│ plan        │       │ permissions │       │ type        │       │ file_name   │
│ quota       │       │ last_used_at│       │ source_fmt  │       │ file_size   │
│ created_at  │       │ expires_at  │       │ target_fmt  │       │ mime_type   │
│ updated_at  │       │ created_at  │       │ options     │       │ checksum    │
└─────────────┘       └─────────────┘       │ progress    │       │ expires_at  │
                                            │ result      │       │ created_at  │
                                            │ error       │       └─────────────┘
                                            │ started_at  │
                                            │ completed_at│
                                            │ created_at  │
                                            └─────────────┘
                                                   │
                                                   │
                                            ┌──────┴──────┐
                                            │ task_logs   │
                                            ├─────────────┤
                                            │ id (PK)     │
                                            │ task_id(FK) │
                                            │ level       │
                                            │ message     │
                                            │ metadata    │
                                            │ created_at  │
                                            └─────────────┘

┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│   batches   │◀──────│ batch_items │       │audit_logs   │
├─────────────┤       ├─────────────┤       ├─────────────┤
│ id (PK)     │       │ id (PK)     │       │ id (PK)     │
│ user_id(FK) │       │ batch_id(FK)│       │ user_id(FK) │
│ total_count │       │ task_id(FK) │       │ action      │
│ completed   │       │ file_index  │       │ resource    │
│ failed      │       │ status      │       │ details     │
│ status      │       │ created_at  │       │ ip_address  │
│ output_fmt  │       └─────────────┘       │ user_agent  │
│ created_at  │                             │ created_at  │
└─────────────┘                             └─────────────┘

┌─────────────┐       ┌─────────────┐
│rate_limits  │       │webhook_deliveries
├─────────────┤       ├─────────────┤
│ id (PK)     │       │ id (PK)     │
│ user_id(FK) │       │ webhook_id  │
│ endpoint    │       │ event_type  │
│ limit       │       │ payload     │
│ window      │       │ response    │
│ current_count│      │ status      │
│ reset_at    │       │ attempts    │
│ created_at  │       │ created_at  │
└─────────────┘       └─────────────┘
```

---

## 2. 表结构定义

### 2.1 users (用户表)

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(100),
    
    -- 订阅计划
    plan VARCHAR(20) DEFAULT 'free' CHECK (plan IN ('free', 'pro', 'enterprise')),
    plan_expires_at TIMESTAMP WITH TIME ZONE,
    
    -- 配额限制
    quota_conversions_per_day INTEGER DEFAULT 100,
    quota_storage_mb INTEGER DEFAULT 1000,
    quota_max_file_size_mb INTEGER DEFAULT 50,
    
    -- 状态
    is_active BOOLEAN DEFAULT true,
    is_verified BOOLEAN DEFAULT false,
    last_login_at TIMESTAMP WITH TIME ZONE,
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 索引
    CONSTRAINT valid_email CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_plan ON users(plan) WHERE plan != 'free';
```

### 2.2 api_keys (API 密钥表)

```sql
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- 密钥信息 (存储哈希值)
    key_hash VARCHAR(255) UNIQUE NOT NULL,
    key_prefix VARCHAR(20) NOT NULL,  -- 用于显示，如 "dfc_pk_"
    
    -- 元数据
    name VARCHAR(100),
    permissions JSONB DEFAULT '["read", "write"]'::jsonb,
    
    -- 使用统计
    last_used_at TIMESTAMP WITH TIME ZONE,
    use_count INTEGER DEFAULT 0,
    
    -- 有效期
    expires_at TIMESTAMP WITH TIME ZONE,
    
    -- 状态
    is_active BOOLEAN DEFAULT true,
    revoked_at TIMESTAMP WITH TIME ZONE,
    revoked_reason TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT valid_permissions CHECK (
        permissions @> '["read"]'::jsonb OR 
        permissions @> '["write"]'::jsonb
    )
);

CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX idx_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_active ON api_keys(is_active, expires_at) 
    WHERE is_active = true;
```

### 2.3 tasks (任务表)

```sql
CREATE TYPE task_status AS ENUM (
    'pending',      -- 等待中
    'processing',   -- 处理中
    'completed',    -- 完成
    'failed',       -- 失败
    'cancelled',    -- 已取消
    'expired'       -- 已过期
);

CREATE TYPE task_type AS ENUM (
    'single',       -- 单文件
    'batch'         -- 批量
);

CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    
    -- 任务类型和状态
    type task_type NOT NULL,
    status task_status DEFAULT 'pending',
    
    -- 批量任务关联
    batch_id UUID,
    batch_index INTEGER,  -- 批量中的序号
    
    -- 文件信息
    source_format VARCHAR(20) NOT NULL,
    target_format VARCHAR(20) NOT NULL,
    original_filename VARCHAR(500),
    original_size BIGINT,
    original_mime_type VARCHAR(100),
    original_checksum VARCHAR(64),  -- SHA-256
    
    -- 转换选项
    options JSONB DEFAULT '{}'::jsonb,
    
    -- 进度信息
    progress_percentage INTEGER DEFAULT 0 CHECK (progress_percentage BETWEEN 0 AND 100),
    current_step VARCHAR(50),
    steps JSONB DEFAULT '[]'::jsonb,  -- [{"name": "upload", "status": "completed", "duration_ms": 500}]
    
    -- 结果信息
    result JSONB,  -- {download_url, file_size, expires_at}
    error JSONB,   -- {code, message, details}
    
    -- 时间戳
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,  -- 结果过期时间
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 性能指标
    queue_time_ms INTEGER,      -- 排队等待时间
    processing_time_ms INTEGER, -- 实际处理时间
    
    -- 回调
    callback_url TEXT,
    callback_delivered BOOLEAN DEFAULT false,
    callback_attempts INTEGER DEFAULT 0
);

CREATE INDEX idx_tasks_user_id ON tasks(user_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_user_status ON tasks(user_id, status);
CREATE INDEX idx_tasks_batch ON tasks(batch_id) WHERE batch_id IS NOT NULL;
CREATE INDEX idx_tasks_created ON tasks(created_at DESC);
CREATE INDEX idx_tasks_expires ON tasks(expires_at) WHERE expires_at IS NOT NULL;
```

### 2.4 batches (批量任务表)

```sql
CREATE TABLE batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- 统计
    total_count INTEGER NOT NULL,
    completed_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    
    -- 状态
    status task_status DEFAULT 'pending',
    
    -- 输出设置
    output_format VARCHAR(20) DEFAULT 'zip',  -- zip, individual
    
    -- 结果
    result JSONB,  -- {download_url, files: []}
    
    -- 时间戳
    completed_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_batches_user_id ON batches(user_id);
CREATE INDEX idx_batches_status ON batches(status);
```

### 2.5 batch_items (批量任务项表)

```sql
CREATE TABLE batch_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id UUID NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    task_id UUID REFERENCES tasks(id) ON DELETE SET NULL,
    
    file_index INTEGER NOT NULL,
    status task_status DEFAULT 'pending',
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(batch_id, file_index)
);

CREATE INDEX idx_batch_items_batch ON batch_items(batch_id);
```

### 2.6 files (文件表)

```sql
CREATE TABLE files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES tasks(id) ON DELETE CASCADE,
    batch_id UUID REFERENCES batches(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    
    -- 存储信息
    storage_key VARCHAR(500) NOT NULL,  -- S3/MinIO key
    storage_bucket VARCHAR(100) DEFAULT 'conversions',
    
    -- 文件元数据
    file_name VARCHAR(500) NOT NULL,
    file_size BIGINT NOT NULL,
    file_format VARCHAR(20) NOT NULL,
    mime_type VARCHAR(100),
    checksum VARCHAR(64),  -- SHA-256
    
    -- 访问统计
    download_count INTEGER DEFAULT 0,
    last_downloaded_at TIMESTAMP WITH TIME ZONE,
    
    -- 有效期
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    deleted_at TIMESTAMP WITH TIME ZONE,  -- 软删除
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT valid_storage CHECK (
        (task_id IS NOT NULL) OR (batch_id IS NOT NULL)
    )
);

CREATE INDEX idx_files_task ON files(task_id);
CREATE INDEX idx_files_batch ON files(batch_id);
CREATE INDEX idx_files_user ON files(user_id);
CREATE INDEX idx_files_expires ON files(expires_at) WHERE deleted_at IS NULL;
```

### 2.7 task_logs (任务日志表)

```sql
CREATE TYPE log_level AS ENUM ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL');

CREATE TABLE task_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    
    level log_level NOT NULL,
    message TEXT NOT NULL,
    
    -- 额外元数据
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- 来源
    source VARCHAR(50),  -- worker, api, converter
    worker_id VARCHAR(100),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_task_logs_task ON task_logs(task_id);
CREATE INDEX idx_task_logs_level ON task_logs(level) WHERE level IN ('ERROR', 'CRITICAL');
CREATE INDEX idx_task_logs_created ON task_logs(created_at DESC);

-- 分区表 (按月)
-- CREATE TABLE task_logs_y2024m01 PARTITION OF task_logs
--     FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

### 2.8 audit_logs (审计日志表)

```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    api_key_id UUID REFERENCES api_keys(id) ON DELETE SET NULL,
    
    -- 操作信息
    action VARCHAR(50) NOT NULL,  -- create_task, download_file, etc.
    resource_type VARCHAR(50),    -- task, file, user
    resource_id UUID,
    
    -- 详情
    details JSONB,
    
    -- 客户端信息
    ip_address INET,
    user_agent TEXT,
    request_id VARCHAR(100),
    
    -- 结果
    success BOOLEAN DEFAULT true,
    error_message TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at DESC);
```

### 2.9 rate_limits (速率限制表)

```sql
CREATE TABLE rate_limits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    api_key_id UUID REFERENCES api_keys(id) ON DELETE CASCADE,
    
    -- 限制定义
    endpoint VARCHAR(100) NOT NULL,  -- /convert, /batch, etc.
    limit_count INTEGER NOT NULL,
    window_seconds INTEGER NOT NULL,
    
    -- 当前状态
    current_count INTEGER DEFAULT 0,
    reset_at TIMESTAMP WITH TIME ZONE NOT NULL,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT valid_limit CHECK (
        (user_id IS NOT NULL) OR (api_key_id IS NOT NULL)
    )
);

CREATE INDEX idx_rate_limits_user ON rate_limits(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX idx_rate_limits_api_key ON rate_limits(api_key_id) WHERE api_key_id IS NOT NULL;
CREATE INDEX idx_rate_limits_reset ON rate_limits(reset_at);
```

### 2.10 webhook_deliveries (Webhook 投递表)

```sql
CREATE TABLE webhook_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- 事件信息
    event_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    
    -- 投递目标
    url TEXT NOT NULL,
    
    -- 响应
    response_status INTEGER,
    response_body TEXT,
    
    -- 投递状态
    status VARCHAR(20) DEFAULT 'pending',  -- pending, delivered, failed
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    
    -- 时间戳
    delivered_at TIMESTAMP WITH TIME ZONE,
    next_attempt_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_webhook_deliveries_user ON webhook_deliveries(user_id);
CREATE INDEX idx_webhook_deliveries_status ON webhook_deliveries(status);
CREATE INDEX idx_webhook_deliveries_next_attempt ON webhook_deliveries(next_attempt_at) 
    WHERE status = 'pending';
```

---

## 3. 视图

### 3.1 用户统计视图

```sql
CREATE VIEW user_stats AS
SELECT 
    u.id AS user_id,
    u.email,
    u.plan,
    COUNT(DISTINCT t.id) AS total_tasks,
    COUNT(DISTINCT t.id) FILTER (WHERE t.status = 'completed') AS completed_tasks,
    COUNT(DISTINCT t.id) FILTER (WHERE t.status = 'failed') AS failed_tasks,
    COALESCE(SUM(f.file_size), 0) AS total_storage_used,
    MAX(t.created_at) AS last_activity_at
FROM users u
LEFT JOIN tasks t ON u.id = t.user_id AND t.created_at > NOW() - INTERVAL '30 days'
LEFT JOIN files f ON t.id = f.task_id AND f.deleted_at IS NULL
GROUP BY u.id, u.email, u.plan;
```

### 3.2 任务统计视图

```sql
CREATE VIEW task_stats_daily AS
SELECT 
    DATE_TRUNC('day', created_at) AS date,
    COUNT(*) AS total_tasks,
    COUNT(*) FILTER (WHERE status = 'completed') AS completed,
    COUNT(*) FILTER (WHERE status = 'failed') AS failed,
    AVG(processing_time_ms) FILTER (WHERE status = 'completed') AS avg_processing_time,
    source_format,
    target_format
FROM tasks
WHERE created_at > NOW() - INTERVAL '90 days'
GROUP BY DATE_TRUNC('day', created_at), source_format, target_format;
```

---

## 4. 函数和触发器

### 4.1 自动更新时间戳

```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tasks_updated_at BEFORE UPDATE ON tasks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_batches_updated_at BEFORE UPDATE ON batches
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### 4.2 任务状态变更触发器

```sql
CREATE OR REPLACE FUNCTION log_task_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO task_logs (task_id, level, message, metadata, source)
        VALUES (
            NEW.id,
            'INFO',
            format('Task status changed from %s to %s', OLD.status, NEW.status),
            jsonb_build_object('old_status', OLD.status, 'new_status', NEW.status),
            'system'
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER task_status_change_trigger
    AFTER UPDATE OF status ON tasks
    FOR EACH ROW
    EXECUTE FUNCTION log_task_status_change();
```

### 4.3 文件过期清理

```sql
CREATE OR REPLACE FUNCTION cleanup_expired_files()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    UPDATE files
    SET deleted_at = NOW()
    WHERE expires_at < NOW() 
      AND deleted_at IS NULL;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;
```

---

## 5. 索引策略

### 5.1 性能优化索引

```sql
-- 复合索引
CREATE INDEX CONCURRENTLY idx_tasks_user_status_created 
    ON tasks(user_id, status, created_at DESC);

CREATE INDEX CONCURRENTLY idx_files_user_expires 
    ON files(user_id, expires_at) 
    WHERE deleted_at IS NULL;

-- 部分索引
CREATE INDEX CONCURRENTLY idx_tasks_pending 
    ON tasks(created_at) 
    WHERE status = 'pending';

CREATE INDEX CONCURRENTLY idx_tasks_processing 
    ON tasks(started_at) 
    WHERE status = 'processing';

-- GIN 索引 (JSONB)
CREATE INDEX CONCURRENTLY idx_tasks_options_gin 
    ON tasks USING GIN (options);

CREATE INDEX CONCURRENTLY idx_tasks_result_gin 
    ON tasks USING GIN (result);
```

---

## 6. 数据保留策略

```sql
-- 自动清理过期数据
CREATE OR REPLACE FUNCTION purge_old_data()
RETURNS void AS $$
BEGIN
    -- 删除 90 天前的任务日志
    DELETE FROM task_logs 
    WHERE created_at < NOW() - INTERVAL '90 days';
    
    -- 删除 180 天前的审计日志
    DELETE FROM audit_logs 
    WHERE created_at < NOW() - INTERVAL '180 days';
    
    -- 删除已完成的 webhook 投递记录
    DELETE FROM webhook_deliveries 
    WHERE status = 'delivered' 
      AND created_at < NOW() - INTERVAL '30 days';
    
    -- 归档旧任务 (可选)
    -- INSERT INTO tasks_archive SELECT * FROM tasks 
    -- WHERE created_at < NOW() - INTERVAL '1 year';
    -- DELETE FROM tasks WHERE created_at < NOW() - INTERVAL '1 year';
END;
$$ LANGUAGE plpgsql;
```

---

## 7. 数据库迁移

### 7.1 Alembic 配置

```python
# alembic.ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os
timezone = UTC

# logging configuration
[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

### 7.2 迁移脚本示例

```python
# alembic/versions/001_initial_schema.py
"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2026-05-18 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('name', sa.String(100)),
        sa.Column('plan', sa.String(20), default='free'),
        sa.Column('plan_expires_at', sa.DateTime(timezone=True)),
        sa.Column('quota_conversions_per_day', sa.Integer, default=100),
        sa.Column('quota_storage_mb', sa.Integer, default=1000),
        sa.Column('quota_max_file_size_mb', sa.Integer, default=50),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('is_verified', sa.Boolean, default=False),
        sa.Column('last_login_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )
    
    # Create other tables...
    # ...


def downgrade():
    op.drop_table('users')
    # Drop other tables...
```

---

## 8. 连接池配置

```python
# database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool

DATABASE_URL = "postgresql+psycopg://user:password@localhost/docconverter"

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

## 9. 备份策略

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backups/postgres"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="docconverter"

# Full backup
pg_dump -Fc -Z9 $DB_NAME > "$BACKUP_DIR/full_$DATE.dump"

# Schema only
pg_dump -s $DB_NAME > "$BACKUP_DIR/schema_$DATE.sql"

# Cleanup old backups (keep 30 days)
find $BACKUP_DIR -name "*.dump" -mtime +30 -delete
find $BACKUP_DIR -name "*.sql" -mtime +30 -delete
```
