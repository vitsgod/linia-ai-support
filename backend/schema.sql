CREATE TABLE IF NOT EXISTS tickets (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name varchar(100) NOT NULL CHECK (char_length(btrim(name)) > 0),
    subject varchar(200) NOT NULL CHECK (char_length(btrim(subject)) > 0),
    description varchar(5000) NOT NULL CHECK (char_length(btrim(description)) > 0),
    status text NOT NULL DEFAULT 'Новая' CHECK (status = 'Новая'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS tickets_created_at_id_idx ON tickets (created_at DESC, id DESC);
