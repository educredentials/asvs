from django.contrib.auth import get_user_model
from rest_framework import serializers
from projects.models import Projects, ProjectMember, ProjectRequirement, RequirementEvidence, RequirementComment, AuditEvent

User = get_user_model()


class ProjectMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectMember
        fields = ['id', 'username', 'role', 'created_at']
        read_only_fields = ['created_at']

    def validate_username(self, value):
        if not User.objects.filter(username=value).exists():
            raise serializers.ValidationError(f"User '{value}' does not exist.")
        return value


class ProjectSerializer(serializers.ModelSerializer):
    members = ProjectMemberSerializer(many=True, read_only=True)
    member_set = ProjectMemberSerializer(many=True, required=False)

    class Meta:
        model = Projects
        fields = ['id', 'project_name', 'project_owner', 'project_description',
                   'project_level', 'asvs_version', 'project_created',
                   'project_allowed_viewers', 'members', 'member_set']
        read_only_fields = ['id', 'project_owner', 'project_created']

    def create(self, validated_data):
        members = validated_data.pop('member_set', [])
        instance = super().create(validated_data)
        for m in members:
            ProjectMember.objects.create(project=instance, **m)
        return instance

    def update(self, instance, validated_data):
        members = validated_data.pop('member_set', None)
        instance = super().update(instance, validated_data)
        if members is not None:
            instance.members.all().delete()
            for m in members:
                ProjectMember.objects.create(project=instance, **m)
        return instance


class RequirementEvidenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequirementEvidence
        fields = ['id', 'title', 'url', 'notes', 'created_by', 'created_at']
        read_only_fields = ['created_at']


class RequirementCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequirementComment
        fields = ['id', 'body', 'created_by', 'created_at']
        read_only_fields = ['created_at']


class ProjectRequirementSerializer(serializers.ModelSerializer):
    evidence = RequirementEvidenceSerializer(many=True, read_only=True)
    comments = RequirementCommentSerializer(many=True, read_only=True)
    evidence_set = RequirementEvidenceSerializer(many=True, required=False)
    comments_set = RequirementCommentSerializer(many=True, required=False)

    class Meta:
        model = ProjectRequirement
        fields = '__all__'

    def create(self, validated_data):
        evidence = validated_data.pop('evidence_set', [])
        comments = validated_data.pop('comments_set', [])
        inst = super().create(validated_data)
        for e in evidence:
            RequirementEvidence.objects.create(requirement=inst, **e)
        for c in comments:
            RequirementComment.objects.create(requirement=inst, **c)
        return inst

    def update(self, instance, validated_data):
        evidence = validated_data.pop('evidence_set', None)
        comments = validated_data.pop('comments_set', None)
        instance = super().update(instance, validated_data)
        if evidence is not None:
            instance.evidence.all().delete()
            for e in evidence:
                RequirementEvidence.objects.create(requirement=instance, **e)
        if comments is not None:
            instance.comments.all().delete()
            for c in comments:
                RequirementComment.objects.create(requirement=instance, **c)
        return instance


class AuditEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = '__all__'
        read_only_fields = ['created_at']
