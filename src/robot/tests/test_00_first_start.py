#
# This test needs to run first. It resets the app state to workaround (yet) unsupported states:
# - therapist user logged in
# - non-English language selected
#

from pathlib import Path

from robot.app import App
from robot.config import get_frame_size, password, username
from robot.navigation import Navigation
from robot.pages import Pages
from robot.reset import reset_app_state, reset_training_and_mood
from robot.tests.shared.browser_actions import login_with_browser_cookie_absent
from robot.tests.test_02_login import _assert_logged_in


async def test_first_start_login(
    app: App, binary_path: Path, navigation: Navigation, test_id
):
    app.close()
    # reset and restart app for first start experience
    reset_app_state()
    reset_training_and_mood()
    await app.find_or_start_by_path(binary_path)
    await app.resize_client_frame(*get_frame_size())
    app.enforce_size()
    await navigation.wait_for_page(Pages.update, timeout=15)
    # the browser might cover the Cynteract window
    await navigation.trigger_transition(Pages.login)

    # The browser form can open without the app showing its legacy Login page.
    # Start browser automation directly instead of waiting for that old screen.
    try:
        await login_with_browser_cookie_absent(username, password, test_id)
    except TimeoutError as login_error:
        # A cached browser session may bypass the form. Only accept that case
        # when the app actually reaches a logged-in page; retain the original
        # browser error otherwise, rather than hiding it behind a generic timeout.
        try:
            await _assert_logged_in(app, navigation, timeout=40)
        except TimeoutError:
            raise login_error
        return

    # assert logged in - app fetches player data ("Checking for your previous data...")
    # after login (browser-based or auto-login) completes, before showing home/introduction
    await _assert_logged_in(app, navigation, timeout=40)
