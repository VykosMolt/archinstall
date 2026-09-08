from collections.abc import Callable
from typing import Any

import pytest

from archinstall.default_profiles.desktops.hyprland import HyprlandProfile
from archinstall.default_profiles.desktops.labwc import LabwcProfile
from archinstall.default_profiles.desktops.niri import NiriProfile
from archinstall.default_profiles.desktops.sway import SwayProfile
from archinstall.default_profiles.desktops.utils import SeatAccess, provision_seat_access
from archinstall.default_profiles.profile import CustomSetting, Profile
from archinstall.lib.models.users import Password, User

SEAT_PROFILES: list[Callable[[], Profile]] = [SwayProfile, HyprlandProfile, NiriProfile, LabwcProfile]


class FakeInstaller:
	def __init__(self) -> None:
		self.commands: list[str] = []

	def arch_chroot(self, cmd: str, *args: Any, **kwargs: Any) -> None:
		self.commands.append(cmd)


def _profile_with(profile_type: Callable[[], Profile], setting: str | None) -> Profile:
	profile = profile_type()
	profile.custom_settings[CustomSetting.SeatAccess] = setting
	return profile


def test_saved_settings_are_read_back() -> None:
	assert SeatAccess.from_setting('seatd') is SeatAccess.Seatd
	assert SeatAccess.from_setting('systemd-logind') is SeatAccess.Logind


def test_the_old_polkit_setting_still_means_logind() -> None:
	assert SeatAccess.from_setting('polkit') is SeatAccess.Logind


def test_nothing_chosen_and_nonsense_both_come_back_empty() -> None:
	assert SeatAccess.from_setting(None) is None
	assert SeatAccess.from_setting('not-a-seat-manager') is None


def test_the_menu_offers_only_the_two_seat_managers() -> None:
	assert [seat.value for seat in SeatAccess] == ['seatd', 'systemd-logind']


def test_seatd_is_installed_and_started() -> None:
	assert SeatAccess.Seatd.packages == ['seatd']
	assert SeatAccess.Seatd.services == ['seatd']


def test_logind_installs_polkit_and_starts_nothing() -> None:
	assert SeatAccess.Logind.packages == ['polkit']
	assert SeatAccess.Logind.services == []


@pytest.mark.parametrize('profile_type', SEAT_PROFILES)
@pytest.mark.parametrize('setting', ['seatd', 'systemd-logind', 'polkit'])
def test_a_profile_installs_whatever_it_starts(profile_type: Callable[[], Profile], setting: str) -> None:
	profile = _profile_with(profile_type, setting)

	assert set(profile.services) <= set(profile.packages)


@pytest.mark.parametrize('profile_type', SEAT_PROFILES)
def test_a_profile_asks_for_nothing_until_a_choice_is_made(profile_type: Callable[[], Profile]) -> None:
	profile = _profile_with(profile_type, None)

	assert profile.services == []
	assert 'seatd' not in profile.packages


def test_seatd_puts_the_users_in_the_seat_group() -> None:
	installer = FakeInstaller()
	users = [User('alice', Password(plaintext='pw'), False), User('bob', Password(plaintext='pw'), False)]

	provision_seat_access(installer, users, 'seatd')  # type: ignore[arg-type]

	assert installer.commands == [
		'usermod -a -G seat alice',
		'usermod -a -G seat bob',
	]


@pytest.mark.parametrize('setting', ['systemd-logind', 'polkit', None])
def test_logind_needs_no_group_membership(setting: str | None) -> None:
	installer = FakeInstaller()
	users = [User('alice', Password(plaintext='pw'), False)]

	provision_seat_access(installer, users, setting)  # type: ignore[arg-type]

	assert installer.commands == []
