import logging

import faker
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from polls.models import Question, Choice
from tests import BaseTestCase, HttpMethod

fake = faker.Faker()

logger = logging.getLogger(__name__)


class QuestionTests(BaseTestCase):
    """
    Given the following failing tests, do what is required externally to this module to make them pass.

    i.e. There should be no changes to this file.  Instead, find the areas in the application to augment
    and fix the failing tests.
    """
    __test__ = True

    def create_question(self):
        pub_date = timezone.make_aware(fake.date_time_this_year())
        question = Question.objects.create(question_text=fake.catch_phrase(), pub_date=pub_date)
        for __ in range(fake.random_digit()):
            Choice.objects.create(question=question, choice_text=fake.bs(), votes=fake.pyint())
        return question

    def test_multi_update(self):
        """
        Augment the endpoint to handle updating multiple objects within a single request.
        """
        # Create some test objects
        expected_count = 10
        self.assertFalse(Question.objects.exists())

        for __ in range(expected_count):
            self.create_question()

        self.assertEqual(Question.objects.count(), expected_count)

        url = reverse("question-list")
        self.authenticate()

        # Build a payload for the request.  In this case we're sending a non-standard payload
        # that includes multiple objects to update.
        payload = []
        for obj in Question.objects.all():
            payload.append(dict(url=reverse("question-detail", kwargs=dict(pk=obj.pk)),
                                question_text=fake.bs()))

        # Send the request - we're doing a partial update in this case (i.e. PATCH vs a PUT)
        response, data = self.request(HttpMethod.PATCH, url, data=payload, authenticated=True)
        self.assertResponseStatus(response, status_code=status.HTTP_200_OK)
        self.assertEqual(len(data["results"]), expected_count)

    def test_has_date_created(self):
        """
        Augment the model to have a `date_created` field.

        This field should be automatically be set with a datetime value representing the point in time
        that the instance was created.  Make sure to create a migration file as well.  (python manage.py makemigrations)

        Furthermore, augment the serializer to include the new field.
        """
        obj = self.create_question()
        url = reverse("question-detail", kwargs=dict(pk=obj.pk))
        response, data = self.request(HttpMethod.GET, url, authenticated=True)
        self.assertResponseStatus(response, status_code=status.HTTP_200_OK)
        self.assertIn("pub_date", data)
        self.assertIn("url", data)
        self.assertIn("question_text", data)
        self.assertIn("choices", data)
        self.assertIn("date_created", data, msg="date_created isn't in the serialized data yet")
        self.assertIsNotNone(data["date_created"])

    def test_query_count_is_off(self):
        """
        Something is causing a higher than expected number of queries executed during a list request.

        Find and fix the area of the application that would be responsible for this.
        """
        # Create a bunch of test objects
        for __ in range(fake.pyint()):
            self.create_question()

        url = reverse("question-list")
        self.authenticate()

        # We only expect 11 queries to execute in total if this request was optimized
        with self.assertNumQueries(11):
            response, data = self.request(HttpMethod.GET, url, authenticated=True)
            self.assertResponseStatus(response, status_code=status.HTTP_200_OK)
            self.assertGreaterEqual(len(data["results"]), 1)
            obj = data["results"][0]
            self.assertIn("pub_date", obj)
            self.assertIn("url", obj)
            self.assertIn("question_text", obj)
            self.assertIn("choices", obj)

    def test_can_edit_question_text_before_votes(self):
        """
        Confirm that editing question_text is allowed when no choices have votes.
        """
        pub_date = timezone.make_aware(fake.date_time_this_year())
        question = Question.objects.create(question_text="Original", pub_date=pub_date)
        Choice.objects.create(question=question, choice_text="Option A", votes=0)

        url = reverse("question-detail", kwargs=dict(pk=question.pk))
        payload = {"question_text": "Updated"}
        response, data = self.request(HttpMethod.PATCH, url, data=payload, authenticated=True)
        self.assertResponseStatus(response, status_code=status.HTTP_200_OK)
        self.assertEqual(data["question_text"], "Updated")

    def test_cannot_edit_question_text_after_votes(self):
        """
        Confirm that editing question_text is not allowed once any choice has votes.
        """
        question = self.create_question()
        original_text = question.question_text
        # Ensure at least one choice has votes
        choice = Choice.objects.filter(question=question).first()
        if choice:
            choice.votes = 5
            choice.save()
        else:
            Choice.objects.create(question=question, choice_text="Voted", votes=5)

        url = reverse("question-detail", kwargs=dict(pk=question.pk))
        payload = {"question_text": "Trying to change this"}
        response, data = self.request(HttpMethod.PATCH, url, data=payload, authenticated=True)
        self.assertResponseStatus(response, status_code=status.HTTP_400_BAD_REQUEST)

        question.refresh_from_db()
        self.assertEqual(question.question_text, original_text)

    def test_voting_from_api(self):
        """
        Verifies that a vote can be cast for a choice via the API, and that the vote count is updated accordingly.
        """
        question = self.create_question()
        choice = Choice.objects.filter(question=question).first()
        self.assertIsNotNone(choice, "Question must have at least one choice")

        original_votes = choice.votes
        url = reverse("question-vote", kwargs=dict(pk=question.pk))
        payload = {"choice_id": choice.pk}
        response, data = self.request(HttpMethod.POST, url, data=payload, authenticated=True)
        self.assertResponseStatus(response, status_code=status.HTTP_200_OK)

        choice.refresh_from_db()
        self.assertEqual(choice.votes, original_votes + 1)
