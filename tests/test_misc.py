import pytest

from slabwatch.bill import clean_ref, parse_history_regex
from slabwatch.gemma import Refused, _extract_json, check_against_previous, validate_bill, validate_meter
from slabwatch.store import rrf_fuse


def test_rrf_prefers_docs_in_both_lists():
    fused = rrf_fuse([[1, 2, 3], [3, 1, 4]])
    assert [d for d, _ in fused][:2] == [1, 3]
    assert fused[0][1] == pytest.approx(1 / 61 + 1 / 62)


def test_meter_low_confidence_is_refused():
    out = validate_meter({"reading_kwh": 1234.5, "display_label": "kWh", "confidence": 0.3, "unreadable_reason": None})
    assert out["reading_kwh"] is None and "low confidence" in out["unreadable_reason"]


def test_meter_good_reading_passes():
    out = validate_meter({"reading_kwh": "04512", "display_label": "1.8.0", "confidence": 0.92, "unreadable_reason": None})
    assert out["reading_kwh"] == 4512.0


@pytest.mark.parametrize("bad", [
    {"reading_kwh": "12a4", "display_label": None, "confidence": 0.9, "unreadable_reason": None},
    {"reading_kwh": 10, "display_label": None, "confidence": 1.5, "unreadable_reason": None},
    {"reading_kwh": 10, "confidence": 0.9, "unreadable_reason": None},
])
def test_meter_invalid_raises(bad):
    with pytest.raises(Refused):
        validate_meter(bad)


def test_extract_json_from_fence():
    assert _extract_json('sure\n```json\n{"a": 1}\n```') == {"a": 1}
    with pytest.raises(Refused):
        _extract_json("no json here")


def test_meter_cannot_go_down():
    assert "lower" in check_against_previous(100, 120, 3)
    assert check_against_previous(130, 120, 3) is None


def test_bill_validation_drops_bad_rows():
    out = validate_bill({"reference_no": "x", "current_units": 180,
                         "history": [{"month": "2026-09", "units": 190}, {"month": "Sep", "units": 1},
                                     {"month": "2026-08", "units": "lots"}]})
    assert out["history"] == [{"month": "2026-09", "units": 190.0, "amount_rs": None}]


def test_bill_regex_history():
    text = "MONTH UNITS BILL PAYMENT\nSEP25 187 6120 6120\nAUG-25 214 14820 14820\nJUL 25 233 16100 0\n"
    h = parse_history_regex(text)
    assert [x["month"] for x in h] == ["2025-07", "2025-08", "2025-09"]
    assert h[-1]["units"] == 187


def test_reference_number_must_be_14_digits():
    assert clean_ref("04 11111 1234567 U") == "04111111234567"
    with pytest.raises(ValueError):
        clean_ref("123")


def test_extract_json_takes_last_object():
    from slabwatch.gemma import _extract_json

    text = 'The prompt says return {"fca_rs_per_unit": null} if absent. Answer: {"fca_rs_per_unit": 1.11, "quote": "x"}'
    assert _extract_json(text)["fca_rs_per_unit"] == 1.11


def test_number_in_quote():
    from slabwatch.tariff import number_in

    assert number_in(1.11, "NEPRA notified the FCA for August 2026 at Rs1.11 per unit")
    assert number_in(0.5, "a cut of 50 paisa per unit")
    assert not number_in(1.11, "NEPRA notified the FCA for August 2026 at Rs1.73 per unit")
