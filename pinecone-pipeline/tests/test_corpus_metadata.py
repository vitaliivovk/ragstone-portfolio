"""Tests for corpus_metadata path → topic derivation."""

import pytest

from corpus_metadata import (
    ROOT_TOPIC_SLUGS,
    SOURCE_DATA_ROOT_SEGMENTS,
    _path_segment_slug,
    derive_corpus_metadata,
)


def test_root_slugs_cover_documented_layout() -> None:
    assert len(ROOT_TOPIC_SLUGS) == len(SOURCE_DATA_ROOT_SEGMENTS)
    assert ROOT_TOPIC_SLUGS[0] == "1_najem_instytucjonalny"
    assert ROOT_TOPIC_SLUGS[1] == "2_najem_firma"
    assert ROOT_TOPIC_SLUGS[2] == "3_mieszkania_z_vatem_najem_zwyky"
    assert ROOT_TOPIC_SLUGS[3] == "4_umowa_rezerwacyjna"
    assert ROOT_TOPIC_SLUGS[4] == "5_instrukcje"
    assert ROOT_TOPIC_SLUGS[5] == "6_program_rabatowy_northwind_club_i_smart_home"
    assert ROOT_TOPIC_SLUGS[6] == "zakwaterowanie"


def test_najem_i_with_utility_subfolder_uses_root_topic() -> None:
    meta = derive_corpus_metadata(
        "1 Najem Instytucjonalny/6 Local power company/Tenant energy notice.docx"
    )
    assert meta["corpusTopic"] == "1_najem_instytucjonalny"
    assert meta["corpusPathPrefix"] == "1_najem_instytucjonalny/6_local_power_company"


def test_najem_i_przedluzenie_subfolder_prefix() -> None:
    meta = derive_corpus_metadata(
        "1 Najem Instytucjonalny/2 Przedłużenie umowy najmu I + OWU + zał 10/"
        "Przedłużenie najmu I (R) PL_16012026_v.9.docx"
    )
    assert meta["corpusTopic"] == "1_najem_instytucjonalny"
    assert meta["corpusPathPrefix"] == "1_najem_instytucjonalny/2_przeduzenie_umowy_najmu_i_owu_za_10"


def test_najem_i_porozumienia_subfolder_prefix() -> None:
    meta = derive_corpus_metadata(
        "1 Najem Instytucjonalny/5 Porozumienia - różne/Porozumienia rozwiązujące/1. standard.docx"
    )
    assert meta["corpusPathPrefix"] == "1_najem_instytucjonalny/5_porozumienia_rozne"


def test_najem_i_annex_folder() -> None:
    meta = derive_corpus_metadata(
        "1 Najem Instytucjonalny/3 Zalaczniki do umów/Zalacznik 1.docx"
    )
    assert meta["corpusTopic"] == "1_najem_instytucjonalny"


def test_najem_firma() -> None:
    meta = derive_corpus_metadata("2 Najem Firma/1 Wzór umowy najmu F/wzór.docx")
    assert meta["corpusTopic"] == "2_najem_firma"


def test_mieszkania_vat() -> None:
    meta = derive_corpus_metadata(
        "3 Mieszkania z vatem- najem zwykły/1 Wzór umowy z vat + OWU + zal 10/x.docx"
    )
    assert meta["corpusTopic"] == "3_mieszkania_z_vatem_najem_zwyky"


def test_umowa_rezerwacyjna() -> None:
    meta = derive_corpus_metadata("4 Umowa rezerwacyjna/Wzór Umowy rezerwacyjnej.docx")
    assert meta["corpusTopic"] == "4_umowa_rezerwacyjna"


def test_instrukcje() -> None:
    meta = derive_corpus_metadata("5 Instrukcje/Instrukcja 2025.pdf")
    assert meta["corpusTopic"] == "5_instrukcje"


def test_northwind_club() -> None:
    meta = derive_corpus_metadata(
        "6 Program rabatowy NORTHWIND CLUB i SMART HOME/Regulamin karty.pdf"
    )
    assert meta["corpusTopic"] == "6_program_rabatowy_northwind_club_i_smart_home"


def test_zakwaterowanie() -> None:
    meta = derive_corpus_metadata(
        "Zakwaterowanie/Proces_zakwaterowania_instrukcja_dla_nowego_pracownika_052026_AP.docx"
    )
    assert meta["corpusTopic"] == "zakwaterowanie"


def test_empty_path_unknown_root() -> None:
    meta = derive_corpus_metadata("")
    assert meta["corpusTopic"] == "unknown_root"


@pytest.mark.parametrize(
    "segment,expected_slug",
    [
        ("1 Najem Instytucjonalny", "1_najem_instytucjonalny"),
        ("3 Mieszkania z vatem- najem zwykły", "3_mieszkania_z_vatem_najem_zwyky"),
    ],
)
def test_path_segment_slug(segment: str, expected_slug: str) -> None:
    assert _path_segment_slug(segment) == expected_slug
