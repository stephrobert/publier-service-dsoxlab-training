# Scenario

Nginx already publishes the application, but the proxy accepts unprotected
admin requests, serves hidden files, and forwards methods the application
does not need.

## Mission

Add security headers, require the supplied credentials on `/admin`, deny
dotfiles, and reject unnecessary write methods without breaking ordinary
application requests.
