package com.netforce;

import com.facebook.react.ReactActivity;
import com.mikemonteith.reactnativempchart.MPChartPackage;
import com.facebook.react.ReactPackage;
import com.facebook.react.shell.MainReactPackage;

import com.AirMaps.AirPackage;
import com.imagepicker.ImagePickerPackage;
import me.nucleartux.date.ReactDatePackage;
import com.oblador.vectoricons.VectorIconsPackage;

import java.util.Arrays;
import java.util.List;

public class MainActivity extends ReactActivity {

    /**
     * Returns the name of the main component registered from JavaScript.
     * This is used to schedule rendering of the component.
     */
    @Override
    protected String getMainComponentName() {
        return "Netforce";
    }

    /**
     * Returns whether dev mode should be enabled.
     * This enables e.g. the dev menu.
     */
    @Override
    protected boolean getUseDeveloperSupport() {
        return BuildConfig.DEBUG;
    }

   /**
   * A list of packages used by the app. If the app uses additional views
   * or modules besides the default ones, add more packages here.
   */
    @Override
    protected List<ReactPackage> getPackages() {
      return Arrays.<ReactPackage>asList(
        new MainReactPackage(),
        new AirPackage(),
        new ImagePickerPackage(),
        new ReactDatePackage(this),
        new VectorIconsPackage(),
        new MPChartPackage()
      );
    }
}