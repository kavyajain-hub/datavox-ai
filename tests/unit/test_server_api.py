from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from server import app

client = TestClient(app)


def test_api_status():
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "provider" in data
    assert "database" in data


def test_api_tables_list():
    response = client.get("/api/tables")
    assert response.status_code == 200
    data = response.json()
    assert "tables" in data
    table_names = [t["name"] for t in data["tables"]]
    assert "customers" in table_names
    assert "products" in table_names


def test_api_table_rows():
    response = client.get("/api/tables/customers?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["table_name"] == "customers"
    assert len(data["rows"]) == 10
    assert "name" in data["columns"]
    assert "email" in data["columns"]


@patch("server.handle_query_detailed")
def test_api_chat_endpoint(mock_handle_query):
    mock_handle_query.return_value = {
        "session_id": "test-session-123",
        "user_query": "Show revenue by region",
        "final_response": "The total revenue is $467,100.",
        "generated_sql": "SELECT region, SUM(total_revenue) FROM regional_sales GROUP BY region;",
        "executed_sql_output": [{"region": "North", "total_revenue": 94100}],
        "node_trace": ["intent_router", "sql_agent", "validation_agent", "execute_agent", "response_agent"],
        "is_safe": True,
        "is_sql_valid": True,
        "validation_error": None,
        "sql_execution_error": None,
        "cached": False
    }

    response = client.post("/api/chat", json={"query": "Show revenue by region"})
    assert response.status_code == 200
    data = response.json()
    assert data["final_response"] == "The total revenue is $467,100."
    assert "SELECT region" in data["generated_sql"]
    assert len(data["node_trace"]) == 5


def test_api_upload_csv_dataset():
    csv_content = (
        "campaign_name,channel,spend,clicks,conversions\n"
        "Spring Sale,Google Ads,1200.50,3400,120\n"
        "Summer Kickoff,Meta Ads,2500.00,7800,310\n"
        "Fall Promo,Email,450.00,1200,95\n"
    )

    files = {
        "file": ("test_campaigns.csv", csv_content.encode("utf-8"), "text/csv")
    }
    data = {
        "table_name": "test_campaigns",
        "description": "Marketing test campaign metrics"
    }

    response = client.post("/api/upload-data", files=files, data=data)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["success"] is True
    assert res_data["details"]["rows_inserted"] == 3

    # Verify new table is listed and rows are accessible
    tables_res = client.get("/api/tables")
    table_names = [t["name"] for t in tables_res.json()["tables"]]
    assert "test_campaigns" in table_names

    rows_res = client.get("/api/tables/test_campaigns")
    assert rows_res.status_code == 200
    assert len(rows_res.json()["rows"]) == 3
    assert rows_res.json()["rows"][0]["campaign_name"] == "Spring Sale"


def test_api_relationships_endpoint():
    response = client.get("/api/relationships")
    assert response.status_code == 200
    data = response.json()
    assert "relationships" in data
    assert len(data["relationships"]) >= 2
    # Verify orders and order_items link exists
    order_rels = [r for r in data["relationships"] if r["from_table"] == "order_items" and r["to_table"] == "orders"]
    assert len(order_rels) > 0
    assert order_rels[0]["from_column"] == "order_id"


def test_api_upload_multiple_related_datasets():
    authors_csv = (
        "author_id,author_name,country\n"
        "1,George Orwell,UK\n"
        "2,Isaac Asimov,USA\n"
    )
    books_csv = (
        "book_id,author_id,title,genre\n"
        "101,1,1984,Dystopian\n"
        "102,1,Animal Farm,Satire\n"
        "103,2,Foundation,Sci-Fi\n"
    )

    files = [
        ("files", ("test_authors.csv", authors_csv.encode("utf-8"), "text/csv")),
        ("files", ("test_books.csv", books_csv.encode("utf-8"), "text/csv"))
    ]

    response = client.post("/api/upload-multiple-data", files=files)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["success"] is True
    assert len(res_data["details"]["tables_ingested"]) == 2

    # Check that relationship test_books.author_id -> test_authors was detected
    rels = res_data["details"]["detected_relationships"]
    author_rels = [r for r in rels if "books" in r["from_table"] and "authors" in r["to_table"]]
    assert len(author_rels) > 0
    assert author_rels[0]["from_column"] == "author_id"

