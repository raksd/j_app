import asyncio


from app import llm
from app.models import Job
from app.services.scoring import combine, find_terms, keyword_match, score_cv
from app.services.scoring.score import LlmScore


def run(coro):
    return asyncio.run(coro)


def test_combine_arithmetic():
    assert combine(50, 80) == round(0.4 * 50 + 0.6 * 80, 1) == 68.0
    assert combine(0, 100) == 60.0
    assert combine(100, 100) == 100.0
    assert combine(33.3, 66.6) == round(0.4 * 33.3 + 0.6 * 66.6, 1)


def test_combine_degrades():
    assert combine(72.5, None) == 72.5
    assert combine(None, 64) == 64.0
    assert combine(None, None) == 0.0


def test_java_does_not_match_javascript():
    assert "java" not in find_terms("We use JavaScript and TypeScript")
    assert "javascript" in find_terms("We use JavaScript")
    assert "java" in find_terms("Backend in Java and Spring")


def test_aliases():
    assert find_terms("deployed on k8s") == {"kubernetes"}
    assert "javascript" in find_terms("front end in JS")
    assert "machine learning" in find_terms("built ML models")
    assert "scikit-learn" in find_terms("used sklearn")
    assert "aws" in find_terms("Amazon Web Services")


def test_short_aliases_are_case_sensitive():
    assert "r" not in find_terms("we go for r and d here")
    assert "go" not in find_terms("ready to go live")
    assert "r" in find_terms("analysis in R and Python")
    assert "go" in find_terms("services written in Go")


def test_no_partial_word_matches():
    assert "sql" not in find_terms("nosqlish")
    assert find_terms("Python3 scripts") == set()  # attached digit, not the word python
    assert "c++" in find_terms("low level C++ code")
    assert "c#" in find_terms("C# and .NET")


def test_keyword_match_scores_share_found():
    score, matched, absent = keyword_match("Python and SQL on Azure", "Needs Python, SQL, Kubernetes and Docker")
    assert score == 50.0
    assert matched == ["python", "sql"]
    assert absent == ["docker", "kubernetes"]


def test_keyword_match_none_when_job_has_no_known_terms():
    score, matched, absent = keyword_match("Python", "Friendly team, good salary")
    assert score is None and matched == [] and absent == []


def test_score_cv_combines_and_cleans_missing(monkeypatch, sample_cv, sample_job):
    async def fake(system, user, schema, max_tokens=0):
        return LlmScore(
            score=70,
            matched=["Python"],
            missing=["Kubernetes", "kubernetes", "Experience with Azure", "Fraud detection experience", ""],
            rationale="Fits well.",
        )

    monkeypatch.setattr(llm, "complete_json", fake)
    result = run(score_cv(sample_cv, sample_job))
    assert result.llm_score == 70
    assert result.ats_score == round(0.4 * result.keyword_score + 0.6 * 70, 1)
    # duplicate removed, and the Azure gap dropped because the CV names Azure
    assert result.missing_requirements == ["Kubernetes", "Fraud detection experience"]
    assert "Python" in result.matched_keywords or "python" in result.matched_keywords


def test_score_cv_clamps_llm_score(monkeypatch, sample_cv, sample_job):
    async def fake(system, user, schema, max_tokens=0):
        return LlmScore(score=140)

    monkeypatch.setattr(llm, "complete_json", fake)
    assert run(score_cv(sample_cv, sample_job)).llm_score == 100


def test_score_cv_degrades_to_keyword_when_llm_fails(monkeypatch, sample_cv, sample_job):
    async def boom(*args, **kwargs):
        raise RuntimeError("usage limit")

    monkeypatch.setattr(llm, "complete_json", boom)
    result = run(score_cv(sample_cv, sample_job))
    assert result.llm_score == 0
    assert result.ats_score == result.keyword_score > 0
    assert "keyword" in result.rationale.lower()
    assert any("kubernetes" in m.lower() for m in result.missing_requirements)


def test_score_cv_with_no_known_job_terms_uses_llm_only(monkeypatch, sample_cv):
    job = Job(id="j2", source="t", title="Helper", company="X", url="https://e.com", description="Friendly team.")

    async def fake(system, user, schema, max_tokens=0):
        return LlmScore(score=55)

    monkeypatch.setattr(llm, "complete_json", fake)
    result = run(score_cv(sample_cv, job))
    assert result.ats_score == 55.0
