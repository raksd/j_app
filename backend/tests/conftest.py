import pytest

from app.models import ExperienceItem, EducationItem, Job, ProjectItem, ScoreResult, StructuredCV


@pytest.fixture
def sample_cv() -> StructuredCV:
    return StructuredCV(
        full_name="JANE EXAMPLE",
        headline="MSc Data Science | BPharm",
        email="jane@example.com",
        phone="07000000000",
        location="Watford, UK",
        summary=(
            "Data Scientist with around 4 years of experience in predictive modelling and machine learning, "
            "after 14+ years in healthcare. Works with clinical and operational stakeholders."
        ),
        skills=[
            "Machine Learning: XGBoost, Random Forest, LSTM",
            "Programming & Data: Python, SQL, Pandas",
            "Cloud & Engineering: Azure, Docker, MLflow",
        ],
        experience=[
            ExperienceItem(
                title="Data Scientist",
                company="Acme Health Trust",
                location="UK",
                start="Feb 2023",
                end="Present",
                bullets=[
                    "Build demand forecasting models in Python using XGBoost and time-based validation.",
                    "Deploy models on Azure with MLflow and monitor how they perform over time.",
                    "Present findings to clinical and operational stakeholders and turn them into service changes.",
                    "Saved around £1M a year by redesigning how community posts are assessed.",
                ],
            ),
            ExperienceItem(
                title="Senior Pharmacist",
                company="High Street Pharmacy",
                location="UK",
                start="Aug 2012",
                end="Jun 2021",
                bullets=["Led recruitment and training of pharmacy staff."],
            ),
        ],
        education=[EducationItem(qualification="MSc Data Science, Merit", institution="University of Sussex, UK")],
        projects=[ProjectItem(name="Bat Classification", description="Built a CNN with TensorFlow to classify bat species.")],
    )


@pytest.fixture
def sample_job() -> Job:
    return Job(
        id="j1",
        source="test",
        title="Data Scientist",
        company="Orbit Bank",
        location="London",
        url="https://example.com/job",
        description=(
            "You will build machine learning models in Python and SQL, deploy them on Azure and monitor them. "
            "You will explain results to stakeholders. Experience with Kubernetes is needed. "
            "Experience of fraud detection is desirable."
        ),
    )


@pytest.fixture
def sample_score() -> ScoreResult:
    return ScoreResult(
        ats_score=0,
        keyword_score=0,
        llm_score=0,
        matched_keywords=["Python", "SQL", "Azure"],
        missing_requirements=["Kubernetes", "Experience of fraud detection"],
    )
