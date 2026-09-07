from rest_framework import serializers


class LeadSerializer(serializers.Serializer):
    fields = serializers.DictField(
        child=serializers.CharField(allow_blank=True),
        required=False,
        default=dict,
    )
    text = serializers.CharField(required=False, allow_blank=True, default="")
    source = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if not attrs.get("fields") and not attrs.get("text"):
            raise serializers.ValidationError("Нужно указать fields или text")
        return attrs
