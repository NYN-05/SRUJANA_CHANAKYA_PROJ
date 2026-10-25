"""One error body for every failure: ``{code, message_en, message_hi, hint}`` (Architecture section 11).
Hindi text is a draft (Q-17). A message never carries chat content, and a response never carries a trace."""

from __future__ import annotations

# code: (HTTP status, English, Hindi, hint)
ERRORS: dict[str, tuple[int, str, str, str]] = {
    "locked": (401, "The vault is locked. Unlock it to continue.", "वॉल्ट बंद है। आगे बढ़ने के लिए उसे खोलें।", "Enter your passphrase to unlock."),
    "wrong_passphrase": (401, "That passphrase did not open the vault.", "यह पासफ़्रेज़ वॉल्ट नहीं खोल सका।", "Check it, or use your recovery key."),
    "forbidden_origin": (403, "This request came from another site and was refused.", "यह अनुरोध किसी और साइट से आया था, इसलिए रोका गया।", "Use the VeriDoc window on this computer."),
    "not_found": (404, "We could not find that.", "यह नहीं मिला।", "Go back and choose it again."),
    "no_vault": (404, "There is no vault here yet.", "यहाँ अभी कोई वॉल्ट नहीं है।", "Create one first."),
    "setup_exists": (409, "A vault already exists here.", "यहाँ पहले से एक वॉल्ट है।", "Unlock it instead."),
    "term_not_confirmable": (409, "This term needs a value from you before it can be confirmed.", "इसे पक्का करने से पहले आपको कीमत भरनी होगी।", "Type the value, then confirm."),
    "nothing_to_version": (409, "Confirm at least one term first.", "पहले कम से कम एक बात पक्की करें।", "Confirm a term, then save a version."),
    "unreadable_file": (400, "We could not read this file. Choose the exported .txt or .zip.", "हम यह फ़ाइल नहीं पढ़ सके। एक्सपोर्ट की हुई .txt या .zip चुनें।", "In WhatsApp, use Export chat and pick Without media or Include media."),
    "bad_selection": (400, "Choose which one is you and who the other person is.", "चुनें कि आप कौन हैं और दूसरा व्यक्ति कौन है।", "Pick two different people from the list, and the date order if asked."),
    "sender_required": (400, "Say who sent this reply.", "बताएँ कि यह जवाब किसने भेजा।", "Choose the sender, or paste the reply with its date and name."),
    "bad_request": (400, "That request could not be used.", "यह अनुरोध इस्तेमाल नहीं हो सका।", "Check what you entered and try again."),
    "too_large": (413, "This file is too large.", "यह फ़ाइल बहुत बड़ी है।", "Export the chat without media, or split it."),
    "invalid_request": (422, "Some of what you entered is not valid.", "आपने जो भरा उसमें कुछ सही नहीं है।", "Check the fields and try again."),
    "internal": (500, "Something went wrong on this computer.", "इस कंप्यूटर पर कुछ गड़बड़ हो गई।", "Try again. Your data was not changed."),
}


class ApiError(Exception):
    """A failure with a fixed code from ``ERRORS``."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code

    @property
    def status(self) -> int:
        return ERRORS[self.code][0]

    def body(self) -> dict[str, str]:
        _, en, hi, hint = ERRORS[self.code]
        return {"code": self.code, "message_en": en, "message_hi": hi, "hint": hint}
