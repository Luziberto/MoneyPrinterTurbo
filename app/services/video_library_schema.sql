-- Video Library schema. Lives in storage/mpt_runtime/videos.db, independent
-- of pipeline/data/pipeline.db -- a video can exist without ever touching a
-- pipeline topic.
--
-- Timestamp convention: every *_at / created_at / updated_at column is TEXT
-- storing a UTC ISO-8601 string (e.g. datetime.now(timezone.utc).isoformat()),
-- matching pipeline/lib/topics.py::utc_now_iso()'s existing convention.

CREATE TABLE IF NOT EXISTS videos (
  id TEXT PRIMARY KEY,               -- == task_id (1:1 cardinality, no separate uuid)
  project_id TEXT,                   -- always NULL today; forward-compat only
  channel_slug TEXT NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  subject TEXT NOT NULL DEFAULT '',
  keywords TEXT NOT NULL DEFAULT '[]',   -- JSON list
  thumbnail_path TEXT,
  video_path TEXT,
  duration_seconds REAL,
  file_size_bytes INTEGER,
  tags TEXT NOT NULL DEFAULT '[]',       -- JSON list
  caption TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'rendering',
  error TEXT,
  pipeline_version TEXT,
  source TEXT NOT NULL DEFAULT 'api',    -- cockpit | pipeline | api | cli | import
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_videos_channel_status ON videos(channel_slug, status);
CREATE INDEX IF NOT EXISTS idx_videos_created_at ON videos(created_at);

CREATE TABLE IF NOT EXISTS video_publications (
  id TEXT PRIMARY KEY,
  video_id TEXT NOT NULL REFERENCES videos(id),
  platform TEXT NOT NULL,            -- tiktok | instagram | youtube | facebook
  provider TEXT NOT NULL,            -- upload-post | zernio | official-api | manual
  status TEXT NOT NULL DEFAULT 'scheduled',  -- scheduled | publishing | published | failed | cancelled
  scheduled_at TEXT,
  published_at TEXT,
  url TEXT,
  error TEXT,
  result TEXT,                       -- JSON, raw backend response
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_video_publications_video_id ON video_publications(video_id);
CREATE INDEX IF NOT EXISTS idx_video_publications_status_scheduled ON video_publications(status, scheduled_at);

CREATE TABLE IF NOT EXISTS video_events (
  id TEXT PRIMARY KEY,
  video_id TEXT NOT NULL REFERENCES videos(id),
  type TEXT NOT NULL,                -- status_changed | stage_completed | published | archived
                                      -- | re_rendered | title_changed | thumbnail_changed
                                      -- | scheduled | cancelled | error
  actor TEXT NOT NULL,               -- system | user | scheduler | api
  created_at TEXT NOT NULL,
  data TEXT                          -- JSON payload, shape depends on `type`
);

CREATE INDEX IF NOT EXISTS idx_video_events_video_created ON video_events(video_id, created_at);
CREATE INDEX IF NOT EXISTS idx_video_events_type_created ON video_events(type, created_at);
