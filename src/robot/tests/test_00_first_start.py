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
from robot.reset import reset_app_state
from robot.tests.shared.browser_actions import login_with_browser_cookie_absent
from robot.tests.test_login import _assert_logged_in


async def test_first_start_login(
    app: App, binary_path: Path, navigation: Navigation, test_id
):
    app.close()
    # reset and restart app for first start experience
    reset_app_state()
    await app.find_or_start_by_path(binary_path)
    await app.resize_client_frame(*get_frame_size())
    app.enforce_size()
    await navigation.wait_for_page(Pages.update, timeout=15)
    # the browser might cover the Cynteract window
    await navigation.trigger_transition(Pages.login)

    # browser login
    await login_with_browser_cookie_absent(username, password, test_id)

    # assert logged in
    await _assert_logged_in(app, navigation, timeout=20)
