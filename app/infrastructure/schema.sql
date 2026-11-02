PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 100),
    email TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin', 'technician')),
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 160),
    description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    price_cents INTEGER NOT NULL CHECK(price_cents >= 0),
    stock INTEGER NOT NULL DEFAULT 0 CHECK(stock >= 0),
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS inventory_movements (
    id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    kind TEXT NOT NULL CHECK(kind IN ('entrada','salida')),
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS repairs (
    id INTEGER PRIMARY KEY,
    tracking_code TEXT NOT NULL UNIQUE,
    device TEXT NOT NULL CHECK(length(trim(device)) BETWEEN 1 AND 160),
    issue TEXT NOT NULL CHECK(length(trim(issue)) BETWEEN 1 AND 2000),
    status TEXT NOT NULL,
    assigned_to INTEGER REFERENCES users(id),
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS repair_history (
    id INTEGER PRIMARY KEY,
    repair_id INTEGER NOT NULL REFERENCES repairs(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id),
    status TEXT NOT NULL,
    internal_note TEXT NOT NULL DEFAULT '',
    public_note TEXT NOT NULL DEFAULT '',
    public_visible INTEGER NOT NULL DEFAULT 0 CHECK(public_visible IN (0,1)),
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_repairs_assigned ON repairs(assigned_to, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_history_repair ON repair_history(repair_id, created_at);
CREATE INDEX IF NOT EXISTS idx_movements_product ON inventory_movements(product_id, created_at DESC);
CREATE TABLE IF NOT EXISTS import_batches (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_proposals (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    operation TEXT NOT NULL CHECK(operation IN ('product_create','stock_move','description')),
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending','approved','cancelled','expired')),
    created_at TEXT NOT NULL,
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS ai_operations (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    operation TEXT NOT NULL,
    product_id INTEGER REFERENCES products(id),
    result TEXT NOT NULL,
    approval_status TEXT NOT NULL CHECK(approval_status IN ('proposed','approved','cancelled','failed')),
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ai_proposals_user ON ai_proposals(user_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_ai_operations_user ON ai_operations(user_id, created_at DESC);
