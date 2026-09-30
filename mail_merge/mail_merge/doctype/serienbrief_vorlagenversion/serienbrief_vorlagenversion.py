from mail_merge.mail_merge.utils.versioning import ImmutableVersionDocument


class SerienbriefVorlagenversion(ImmutableVersionDocument):
	"""Fester Meilenstein oder kurzfristig zusammengefasster, unbenannter Arbeitsstand."""

	_IMMUTABLE_FIELDS = (
		"vorlage",
		"version_number",
		"source",
		"change_summary",
		"restored_from",
		"based_on",
		"assistant_created",
		"content_hash",
		"snapshot",
		"textbaustein_versionen",
	)
