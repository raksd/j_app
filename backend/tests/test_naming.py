from app.services.naming import document_name, initials


def test_initials_from_full_name():
    assert initials("Rakhee Dudhal") == "RD"
    assert initials("jane  example") == "JE"
    assert initials("") == ""


def test_document_name_uses_initials_and_company():
    assert document_name("CV", "Rakhee Dudhal", "Acme Ltd", "docx") == "RD_CV_Acme_Ltd.docx"
    assert document_name("Cover_Letter", "Rakhee Dudhal", "Acme Ltd", "txt") == "RD_Cover_Letter_Acme_Ltd.txt"


def test_document_name_is_safe_for_filesystems():
    name = document_name("CV", "Rakhee Dudhal", "A/B: C*Corp? <x>", "docx")
    assert name == "RD_CV_A_B_C_Corp_x.docx"
    assert not any(ch in name for ch in '\\/:*?"<>|')


def test_document_name_without_company_or_name():
    assert document_name("CV", "Rakhee Dudhal", "", "docx") == "RD_CV.docx"
    assert document_name("CV", "", "Acme", "docx") == "CV_Acme.docx"
    assert len(document_name("CV", "A B", "x" * 200, "docx")) < 60
