from urllib.parse import urlparse

from django.contrib.auth.models import User, Group
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.urls import Resolver404, resolve
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from polls.models import Question, Choice
from .serializers import (
    BulkQuestionSerializer,
    ChoiceSerializer,
    GroupSerializer,
    QuestionSerializer,
    UserSerializer,
)


class UserViewSet(viewsets.ModelViewSet):
    """API endpoint that allows users to be viewed or edited."""
    queryset = User.objects.all().order_by("-date_joined")
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]


class GroupViewSet(viewsets.ModelViewSet):
    """API endpoint that allows groups to be viewed or edited."""
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated]


def _question_pk_from_url(url):
    """
    Resolve a hyperlinked question URL to its primary key.

    Returns ``None`` for anything that isn't a valid ``question-detail`` URL
    — including Choice URLs, arbitrary paths, or missing values — so callers
    can surface a clean 400 instead of silently mutating the wrong record.
    """
    if not url or not isinstance(url, str):
        return None
    try:
        match = resolve(urlparse(url).path)
    except Resolver404:
        return None
    if match.url_name != "question-detail":
        return None
    pk = match.kwargs.get("pk")
    # ``resolve`` returns URL kwargs as strings; coerce to the integer PK
    # Question actually uses so downstream lookups (e.g. ``in_bulk``) match.
    try:
        return int(pk)
    except (TypeError, ValueError):
        return None


class QuestionViewSet(viewsets.ModelViewSet):
    """API endpoint that allows questions to be viewed, edited, and voted on."""
    queryset = Question.objects.all().prefetch_related("choice_set")
    serializer_class = QuestionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "partial_update_list":
            return BulkQuestionSerializer
        return super().get_serializer_class()

    def partial_update_list(self, request, *args, **kwargs):
        """
        PATCH on the list endpoint: partial-update many questions in one call.

        Expects a JSON array of objects, each identifying its target via the
        hyperlinked ``url`` field.  The whole batch runs inside a single
        transaction so a validation failure on any item rolls the rest back
        — callers get all-or-nothing semantics.
        """
        data = request.data
        if not isinstance(data, list):
            return Response(
                {"detail": "Expected a list of objects to update."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not data:
            return Response({"results": []}, status=status.HTTP_200_OK)

        pks = []
        for index, item in enumerate(data):
            if not isinstance(item, dict):
                return Response(
                    {"detail": f"Entry {index} must be an object."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            pk = _question_pk_from_url(item.get("url"))
            if pk is None:
                return Response(
                    {"detail": f"Entry {index} is missing a valid question `url`."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            pks.append(pk)

        # Fetch every target in a single query, rather than N individual
        # lookups.  ``in_bulk`` returns a {pk: instance} dict.
        instances = self.get_queryset().in_bulk(pks)
        missing = [pk for pk in pks if pk not in instances]
        if missing:
            return Response(
                {"detail": f"Question(s) not found: {missing}"},
                status=status.HTTP_404_NOT_FOUND,
            )

        results = []
        with transaction.atomic():
            for item, pk in zip(data, pks):
                serializer = self.get_serializer(instances[pk], data=item, partial=True)
                serializer.is_valid(raise_exception=True)
                serializer.save()
                results.append(serializer.data)

        return Response({"results": results}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_name="vote")
    def vote(self, request, pk=None):
        """
        Cast a single vote for ``choice_id`` on this question.

        The increment uses an ``F`` expression so concurrent voters can't
        clobber each other's writes at the database level.
        """
        question = self.get_object()
        choice_id = request.data.get("choice_id")
        if choice_id is None:
            return Response(
                {"detail": "`choice_id` is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        choice = get_object_or_404(question.choice_set, pk=choice_id)
        Choice.objects.filter(pk=choice.pk).update(votes=F("votes") + 1)
        choice.refresh_from_db()

        serializer = ChoiceSerializer(choice, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)


class ChoiceViewSet(viewsets.ModelViewSet):
    """API endpoint that allows choices to be viewed or edited."""
    queryset = Choice.objects.all()
    serializer_class = ChoiceSerializer
    permission_classes = [permissions.IsAuthenticated]
