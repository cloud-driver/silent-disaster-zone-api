import unittest

from fastapi.testclient import TestClient

from src.api.main import app


class ApiDocsTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_api_number_is_shown(self):
        response = self.client.get("/openapi.json")

        self.assertEqual(response.status_code, 200)

        schema = response.json()

        operation = schema["paths"][
            "/silent-risk"
        ]["get"]

        self.assertEqual(
            operation["summary"],
            "【10-1】查詢沉默災區風險清單",
        )

        self.assertEqual(
            operation["operationId"],
            "api_10_1",
        )

    def test_query_input_has_description_and_default(self):
        response = self.client.get("/openapi.json")

        schema = response.json()

        parameters = schema["paths"][
            "/silent-risk"
        ]["get"]["parameters"]

        level_parameter = next(
            parameter
            for parameter in parameters
            if parameter["name"] == "level"
        )

        self.assertIn(
            "**必填：** 否",
            level_parameter["description"],
        )

        self.assertIn(
            "**預設值：** `null`",
            level_parameter["description"],
        )

    def test_admin_endpoint_has_security(self):
        response = self.client.get("/openapi.json")

        schema = response.json()

        operation = schema["paths"][
            "/reports/pending"
        ]["get"]

        self.assertEqual(
            operation["security"],
            [
                {
                    "BearerAccessToken": [],
                    "ReportAdminKey": [],
                }
            ],
        )

    def test_review_body_marks_required_and_default(self):
        response = self.client.get("/openapi.json")

        schema = response.json()

        review_schema = schema["components"][
            "schemas"
        ]["ReviewRequest"]

        self.assertIn(
            "decision",
            review_schema["required"],
        )

        self.assertEqual(
            review_schema["properties"][
                "reviewer_id"
            ]["default"],
            "admin",
        )

    def test_swagger_ui_loads(self):
        response = self.client.get("/docs")

        self.assertEqual(response.status_code, 200)

        self.assertIn(
            "Silent Disaster Zone API Portal",
            response.text,
        )


if __name__ == "__main__":
    unittest.main()