import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from control_app import ControlWindow

class WallpaperControlsTest(unittest.TestCase):
    def fake(self):
        return SimpleNamespace(_loading=False,values={'enabled':True},status=Mock(),_sync_wallpaper_power=Mock())

    def test_power_switch_requests_real_extension_handover(self):
        obj=self.fake()
        with patch('control_app.save_settings'),patch('control_app.subprocess.run') as run:
            for active in [False,True]:
                ControlWindow._set(obj,'enabled',active)
                self.assertEqual(run.call_args.args[0],['gnome-extensions','enable' if active else 'disable','factory-observatory@progretech.com'])

    def test_loading_and_unrelated_settings_do_not_enable_wallpaper(self):
        obj=self.fake()
        with patch('control_app.save_settings'),patch('control_app.subprocess.run') as run:
            obj._loading=True;ControlWindow._set(obj,'enabled',True)
            obj._loading=False;ControlWindow._set(obj,'glow',.5)
            run.assert_not_called()

    def test_failure_is_visible_and_switch_resynchronizes(self):
        obj=self.fake()
        with patch('control_app.save_settings'),patch('control_app.subprocess.run',side_effect=OSError('not installed')):
            ControlWindow._set(obj,'enabled',True)
        obj.status.set_text.assert_called_once()
        obj._sync_wallpaper_power.assert_called_once()

    def test_external_handover_updates_switch_without_writing_settings(self):
        obj=self.fake();obj.power_switch=Mock();obj._shell_settings=Mock()
        obj._shell_settings.get_strv.side_effect=lambda key: ['avalon@progretech.com'] if key=='enabled-extensions' else []
        obj._shell_settings.get_boolean.return_value=False
        ControlWindow._sync_wallpaper_power(obj)
        obj.power_switch.set_active.assert_called_once_with(False)
        self.assertFalse(obj._loading)

if __name__=='__main__':unittest.main()
