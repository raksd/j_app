from __future__ import annotations

import re

# canonical name -> spellings that count as the same thing. Short or ambiguous spellings
# (ML, JS, R, Go) are matched case-sensitively so "go" or "r" in ordinary prose never counts.
VOCAB: dict[str, list[str]] = {
    "python": ["python"],
    "r": ["R"],
    "sql": ["sql", "t-sql", "tsql"],
    "pyspark": ["pyspark"],
    "spark": ["spark", "apache spark"],
    "scala": ["scala"],
    "java": ["java"],
    "javascript": ["javascript", "JS", "ecmascript"],
    "typescript": ["typescript", "TS"],
    "c++": ["c++"],
    "c#": ["c#", "csharp"],
    ".net": [".net", "dotnet"],
    "go": ["Go", "golang"],
    "rust": ["rust"],
    "sas": ["SAS"],
    "matlab": ["matlab"],
    "react": ["react", "reactjs", "react.js"],
    "node": ["node.js", "nodejs"],
    "docker": ["docker"],
    "kubernetes": ["kubernetes", "k8s"],
    "git": ["git", "github", "gitlab"],
    "ci/cd": ["ci/cd", "cicd", "continuous integration", "continuous delivery", "continuous deployment"],
    "azure": ["azure"],
    "aws": ["aws", "amazon web services"],
    "gcp": ["gcp", "google cloud"],
    "cloud": ["cloud"],
    "databricks": ["databricks"],
    "snowflake": ["snowflake"],
    "microsoft fabric": ["microsoft fabric"],
    "airflow": ["airflow"],
    "mlflow": ["mlflow"],
    "mlops": ["mlops"],
    "azure devops": ["azure devops"],
    "terraform": ["terraform"],
    "power bi": ["power bi", "powerbi"],
    "tableau": ["tableau"],
    "excel": ["excel"],
    "looker": ["looker"],
    "pandas": ["pandas"],
    "numpy": ["numpy"],
    "scipy": ["scipy"],
    "scikit-learn": ["scikit-learn", "sklearn", "scikit learn"],
    "tensorflow": ["tensorflow"],
    "keras": ["keras"],
    "pytorch": ["pytorch"],
    "xgboost": ["xgboost"],
    "lightgbm": ["lightgbm"],
    "random forest": ["random forest", "random forests"],
    "machine learning": ["machine learning", "ML"],
    "deep learning": ["deep learning"],
    "neural networks": ["neural network", "neural networks"],
    "nlp": ["nlp", "natural language processing"],
    "llm": ["llm", "llms", "large language model", "large language models"],
    "generative ai": ["generative ai", "genai", "gen ai"],
    "agentic ai": ["agentic ai", "ai agents", "agentic"],
    "rag": ["rag", "retrieval-augmented generation", "retrieval augmented generation"],
    "fine-tuning": ["fine-tuning", "fine tuning", "finetuning", "fine-tuned"],
    "computer vision": ["computer vision"],
    "transformers": ["transformers", "transformer models"],
    "bert": ["bert"],
    "lstm": ["lstm"],
    "cnn": ["cnn", "cnns", "convolutional neural network"],
    "forecasting": ["forecasting", "time series", "time-series"],
    "regression": ["regression"],
    "classification": ["classification"],
    "clustering": ["clustering"],
    "statistics": ["statistics", "statistical analysis", "statistical modelling", "statistical modeling"],
    "bayesian": ["bayesian"],
    "causal inference": ["causal inference", "causal"],
    "a/b testing": ["a/b testing", "ab testing", "a/b tests", "experimentation"],
    "optimisation": ["optimisation", "optimization"],
    "simulation": ["simulation", "simulations"],
    "risk modelling": ["risk modelling", "risk modeling", "risk models"],
    "model monitoring": ["model monitoring", "model drift", "drift detection"],
    "model deployment": ["model deployment", "deploying models", "deploy models"],
    "feature engineering": ["feature engineering"],
    "data pipelines": ["data pipeline", "data pipelines", "etl", "elt"],
    "data modelling": ["data modelling", "data modeling"],
    "data warehouse": ["data warehouse", "data warehousing"],
    "data visualisation": ["data visualisation", "data visualization", "dashboards", "dashboard"],
    "data governance": ["data governance"],
    "data quality": ["data quality"],
    "api": ["api", "apis", "rest api", "restful"],
    "agile": ["agile", "scrum", "kanban"],
    "stakeholder management": ["stakeholder", "stakeholders"],
    "geospatial": ["geospatial", "gis", "qgis", "geopandas"],
    "graph analytics": ["networkx", "graph theory", "graph analytics"],
    "spacy": ["spacy"],
    "nltk": ["nltk"],
    "faiss": ["faiss"],
    "lora": ["lora"],
    "sentence-transformers": ["sentence-transformers", "sentence transformers"],
    "nosql": ["nosql", "mongodb", "cassandra"],
    "postgresql": ["postgresql", "postgres"],
    "linux": ["linux"],
    "healthcare": ["healthcare", "nhs", "clinical"],
    "population health": ["population health"],
    "gdpr": ["gdpr"],
    "model risk governance": ["model risk", "model-risk"],
    "fraud": ["fraud"],
    "reproducible analytical pipelines": ["rap", "reproducible analytical pipeline", "reproducible analytical pipelines"],
}


def _pattern(alias: str) -> re.Pattern[str]:
    case_sensitive = len(alias) <= 3 and alias != alias.lower() or alias == "Go"
    body = re.escape(alias)
    boundary = rf"(?<![A-Za-z0-9+#.]){body}(?![A-Za-z0-9+#&])"
    return re.compile(boundary, 0 if case_sensitive else re.IGNORECASE)


_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    canon: [_pattern(a) for a in aliases] for canon, aliases in VOCAB.items()
}


def find_terms(text: str) -> set[str]:
    """Canonical vocabulary terms present in `text`, with whole-word matching."""
    return {canon for canon, pats in _PATTERNS.items() if any(p.search(text) for p in pats)}
