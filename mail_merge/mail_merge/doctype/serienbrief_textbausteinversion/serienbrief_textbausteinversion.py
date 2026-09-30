from mail_merge.mail_merge.utils.versioning import ImmutableVersionDocument


class SerienbriefTextbausteinversion(ImmutableVersionDocument):
	"""Fester Meilenstein oder kurzfristig zusammengefasster, unbenannter Arbeitsstand eines Bausteins."""

	_IMMUTABLE_FIELDS = (
		"textbaustein",
		"version_number",
		"source",
		"change_summary",
		"restored_from",
		"content_hash",
		"snapshot",
	)
