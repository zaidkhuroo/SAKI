from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, UserProfile, UserAddress
# users/serializers.py
from dj_rest_auth.registration.serializers import RegisterSerializer
from rest_framework import serializers

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)

    class Meta:
        model = User
        fields = ('email', 'password', 'confirm_password', 'first_name', 'last_name')

    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError("Passwords do not match")
        return attrs

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        user = User.objects.create_user(email=validated_data['email'], password=validated_data['password'])
        # Create user profile
        UserProfile.objects.create(
            user=user,
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name']
        )
        return user

class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            user = User.objects.filter(email=email).first()
            if user and user.check_password(password):
                refresh = RefreshToken.for_user(user)
                return {
                    'user': user,
                    'access_token': str(refresh.access_token),
                    'refresh_token': str(refresh)
                }
            raise serializers.ValidationError('Invalid credentials')
        raise serializers.ValidationError('Email and password are required')

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ('first_name', 'last_name', 'date_of_birth')

class UserAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAddress
        fields = ('street', 'city', 'pincode')

class UserDetailSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer()
    address = UserAddressSerializer( required=False)

    class Meta:
        model = User
        fields = ('email', 'date_joined', 'profile', 'address')




class CustomRegisterSerializer(RegisterSerializer):
    username = None  # remove username field
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)

    def get_cleaned_data(self):
        data = super().get_cleaned_data()
        data['first_name'] = self.validated_data.get('first_name', '')
        data['last_name'] = self.validated_data.get('last_name', '')
        return data

 