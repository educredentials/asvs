from django.shortcuts import render, redirect
from user_agents import parse



def home_page(request):
    # SURFconext-authenticated users are exempt from the local TOTP 2FA
    # requirement (institutional SSO is their trusted authentication factor),
    # so their is_two_factor_enabled flag must not be recomputed/reset here.
    if request.user.is_authenticated and request.user.auth_source != request.user.AUTH_SOURCE_OIDC:
        request.user.is_two_factor_enabled = False
        verified_devices = request.user.totpdevice_set.filter(confirmed=True)
        current_device_name = str(parse(request.META.get('HTTP_USER_AGENT', 'unknown')))
        for device in verified_devices:
            if current_device_name == device.name:
                request.user.is_two_factor_enabled = True
                break
        request.user.save(update_fields=['is_two_factor_enabled'])
    if request.user.is_authenticated and request.user.is_two_factor_enabled is False:
            return redirect("authenticate_2fa")
    return render(request, 'home/home.html')
