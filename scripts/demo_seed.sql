-- Demo schema + data for pg-backup-validator end-to-end test.
CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, email TEXT NOT NULL UNIQUE, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS orders (id SERIAL PRIMARY KEY, user_id INT NOT NULL REFERENCES users(id), amount_cents INT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
INSERT INTO users (email) VALUES ('alice@example.com'), ('bob@example.com'), ('carol@example.com') ON CONFLICT (email) DO NOTHING;
INSERT INTO orders (user_id, amount_cents) SELECT id, 1000 + id * 50 FROM users ON CONFLICT DO NOTHING;
