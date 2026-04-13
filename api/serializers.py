from django.contrib.auth.models import User, Group
from rest_framework import serializers

from polls.models import Question, Choice


class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = ["url", "username", "email", "groups"]


class GroupSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Group
        fields = ["url", "name"]


class ChoiceSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Choice
        fields = ["url", "votes", "choice_text"]


class QuestionSerializer(serializers.HyperlinkedModelSerializer):
    choices = ChoiceSerializer(source="choice_set", many=True, read_only=True)

    class Meta:
        model = Question
        fields = ["url", "question_text", "pub_date", "date_created", "choices"]
        read_only_fields = ["date_created"]

    def validate_question_text(self, value):
        """
        Once any choice has received votes, the question text is frozen.
        This keeps the historical record of what respondents were actually
        answering when they cast their votes.
        """
        instance = self.instance
        if instance is None or value == instance.question_text:
            return value

        if instance.choice_set.filter(votes__gt=0).exists():
            raise serializers.ValidationError(
                "Cannot edit question_text once any choice has received votes."
            )
        return value


class BulkQuestionSerializer(QuestionSerializer):
    """
    Variant used by the bulk partial-update endpoint.

    Bulk updates are an admin-oriented operation (e.g. fixing typos across
    many questions at once) and intentionally bypass the per-question vote
    lock enforced by the standard detail endpoint.  Using a distinct
    serializer class makes that policy explicit rather than hiding it behind
    a flag.
    """

    def validate_question_text(self, value):
        return value
