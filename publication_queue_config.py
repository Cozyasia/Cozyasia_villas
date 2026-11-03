"""Publication queue configuration, no secrets and no Telegram side effects."""
QUEUE_TAB = "PublicationQueue"
CHANNEL = "arenda_vill_samui"
READY = "ready"
PROCESSING = "processing"
PUBLISHED = "published"
FAILED = "failed"
FIELDS = ("lot", "status", "caption_html", "photo_drive_ids", "telegram_url", "error")
