CREATE TABLE IF NOT EXISTS topics (
  uid TEXT PRIMARY KEY,
  channel_slug TEXT NOT NULL,
  topic_id INTEGER NOT NULL,
  category TEXT NOT NULL,
  topic TEXT NOT NULL,
  topic_hash TEXT NOT NULL,
  music_profiles TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  generated_at TEXT,
  task_id TEXT,
  video_path TEXT,
  approved INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_topics_channel_topic_id
  ON topics(channel_slug, topic_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_topics_channel_hash
  ON topics(channel_slug, topic_hash);

CREATE INDEX IF NOT EXISTS idx_topics_channel_status
  ON topics(channel_slug, status);
