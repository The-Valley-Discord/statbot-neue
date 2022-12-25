PRAGMA journal_mode = WAL;

CREATE TABLE messages (
	message_id INTEGER PRIMARY KEY,
	guild_id INTEGER NOT NULL,
	channel_id INTEGER NOT NULL,
	category_id INTEGER,
	thread_id INTEGER,
	content_length INTEGER NOT NULL,
	content_words INTEGER NOT NULL,
	content_has_attachments BOOLEAN NOT NULL,
	user_hours_on_server INTEGER,
	-- contains the set of demographic roles the posting user is in
	-- e.g. @transmasculine, @agender, @;; etc.
	user_demographic INTEGER NOT NULL
);

CREATE TABLE channel_tags (
	channel_id INTEGER PRIMARY KEY,
	guild_id INTEGER NOT NULL,
	tag TEXT NOT NULL
);
