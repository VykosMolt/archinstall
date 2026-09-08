from enum import Enum

from archinstall.default_profiles.profile import CustomSetting, Profile
from archinstall.lib.installer import Installer
from archinstall.lib.log import warn
from archinstall.lib.menu.helpers import Selection
from archinstall.lib.models.users import User
from archinstall.lib.translationhandler import tr
from archinstall.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.result import ResultType

_LEGACY_LOGIND_SETTING = 'polkit'


class SeatAccess(Enum):
	Seatd = 'seatd'
	Logind = 'systemd-logind'

	@classmethod
	def from_setting(cls, value: str | None) -> SeatAccess | None:
		if value is None:
			return None

		if value == _LEGACY_LOGIND_SETTING:
			return cls.Logind

		try:
			return cls(value)
		except ValueError:
			warn(f'Unknown seat access setting, ignoring it: {value}')
			return None

	@property
	def packages(self) -> list[str]:
		match self:
			case SeatAccess.Seatd:
				return ['seatd']
			case SeatAccess.Logind:
				# logind uses polkit for unprivileged authorization.
				return ['polkit']

	@property
	def services(self) -> list[str]:
		match self:
			case SeatAccess.Seatd:
				return ['seatd']
			case SeatAccess.Logind:
				# systemd-logind.service is static.
				return []


def seat_access_of(profile: Profile) -> SeatAccess | None:
	return SeatAccess.from_setting(profile.custom_settings.get(CustomSetting.SeatAccess))


def provision_seat_access(
	install_session: Installer,
	users: list[User],
	seat_access: str,
) -> None:
	if SeatAccess.from_setting(seat_access) is SeatAccess.Seatd:
		for user in users:
			install_session.arch_chroot(f'usermod -a -G seat {user.username}')


async def select_seat_access(profile_name: str, default: str | None) -> SeatAccess:
	header = tr('{} needs access to your seat').format(profile_name)
	header += f' ({tr("collection of hardware devices i.e. keyboard, mouse")})' + '\n'
	header += tr('Choose an option how to give {} access to your hardware').format(profile_name)

	items = [MenuItem(s.value, value=s) for s in SeatAccess]
	group = MenuItemGroup(items, sort_items=True)

	group.set_default_by_value(SeatAccess.from_setting(default))

	result = await Selection[SeatAccess](
		group,
		header=header,
		allow_skip=False,
	).show()

	if result.type_ == ResultType.Selection:
		return result.get_value()
	else:
		raise ValueError('Unexpected result type from seat access selection')
