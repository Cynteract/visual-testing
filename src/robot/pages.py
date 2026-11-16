from enum import Enum


class Pages(Enum):
    # not logged in
    login = "login"
    login_help = "help"
    startup = "startup"
    update = "update"
    therapist_page = "therapist_page"
    # home user
    achievements = "achievements"
    buddy_page = "buddy_page"
    game_center = "game_center"
    help_page = "help_page"
    home = "home"
    introduction = "introduction"
    please_connect = "please_connect"
    position_selection = "position_selection"
    settings = "settings"
    # game
    calibrate = "calibrate"
    feedback = "feedback"
    gameplay = "sphere_runner"
    movement_selection = "movement_selection"
    pause_menu = "pause_menu"
    weekly_results = "weekly_results"
    # meta
    _restart = "_restart"

    def has(self, tag: "PageTags") -> bool:
        return tag in _page_tags[self]


class PageTags(Enum):
    game = "game"
    any = "any"
    device_connected = "device_connected"


_page_tags = {
    # not logged in
    Pages.login_help: [PageTags.any],
    Pages.login: [PageTags.any],
    Pages.startup: [PageTags.any],
    Pages.update: [PageTags.any],
    Pages.therapist_page: [PageTags.any],
    # home user
    Pages.achievements: [PageTags.any],
    Pages.buddy_page: [PageTags.any],
    Pages.game_center: [PageTags.any, PageTags.device_connected],
    Pages.help_page: [PageTags.any],
    Pages.home: [PageTags.any],
    Pages.introduction: [PageTags.any],
    Pages.please_connect: [PageTags.any, PageTags.game],
    Pages.position_selection: [PageTags.any, PageTags.device_connected],
    Pages.settings: [PageTags.any],
    # game
    Pages.calibrate: [PageTags.any, PageTags.device_connected, PageTags.game],
    Pages.feedback: [PageTags.any, PageTags.device_connected, PageTags.game],
    Pages.gameplay: [PageTags.any, PageTags.device_connected, PageTags.game],
    Pages.movement_selection: [PageTags.any, PageTags.device_connected, PageTags.game],
    Pages.pause_menu: [PageTags.any, PageTags.device_connected, PageTags.game],
    Pages.weekly_results: [PageTags.any, PageTags.device_connected, PageTags.game],
    # meta
    Pages._restart: [],
}

for page in Pages:
    assert page in _page_tags, f"Page {page} is missing tags"
