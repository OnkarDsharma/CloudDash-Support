from knowledge_base.ingest import load_articles


def test_loads_required_number_of_articles() -> None:
    articles = load_articles()

    assert len(articles) >= 15


def test_articles_have_required_categories() -> None:
    categories = {article.category for article in load_articles()}

    assert "faq" in categories
    assert "troubleshooting" in categories
    assert "billing_policy" in categories
    assert "api_documentation" in categories
    assert "account_access" in categories


def test_articles_have_required_metadata() -> None:
    articles = load_articles()

    for article in articles:
        assert article.id.startswith("KB-")
        assert article.title
        assert article.category
        assert article.tags
        assert article.content
        assert article.last_updated
        assert article.applies_to


def test_demo_scenarios_are_covered() -> None:
    articles = load_articles()
    all_text = " ".join(
        f"{article.title} {' '.join(article.tags)} {article.content}".lower()
        for article in articles
    )

    assert "alerts stop firing after aws integration credentials" in all_text
    assert "sso is available for enterprise workspaces" in all_text
    assert "upgrades from pro to enterprise" in all_text
    assert "duplicate charge" in all_text
    assert "immediate refunds and manager requests must be escalated" in all_text
    assert "does not currently provide a documented datadog integration" in all_text
