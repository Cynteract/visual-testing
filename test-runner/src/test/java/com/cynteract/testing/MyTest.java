package com.cynteract.testing;

import static org.junit.jupiter.api.Assertions.assertNotNull;

import java.io.FileInputStream;
import java.io.IOException;
import java.util.Properties;
import org.junit.jupiter.api.Test;
import org.sikuli.script.App;
import org.sikuli.script.FindFailed;
import org.sikuli.script.ImagePath;
import org.sikuli.script.Key;
import org.sikuli.script.Screen;

public class MyTest {

  private Properties getEnv() {
    Properties properties = new Properties();
    try (FileInputStream fis = new FileInputStream("../.env")) {
      properties.load(fis);
    } catch (IOException e) {
      throw new RuntimeException("Failed to load .env file", e);
    }
    return properties;
  }

  @Test
  public void testSomething() throws FindFailed {
    ImagePath.add("src/test/resources/images/");
    Properties env = getEnv();
    Screen screen = new Screen(1);
    App.open(env.getProperty("BINARY_PATH"));
    // screen.wait("LoginLink.png", 20);

    // Login
    screen.click("LoginLink.png");
    screen.click("Email.png");
    screen.type(env.getProperty("USER"));
    screen.type(Key.TAB);
    screen.type(env.getProperty("PASSWORD"));
    screen.click("LoginButton.png");

    // Game center
    screen.click("Game_center.png");
    assertNotNull(
      screen.wait("Please_connect.png", 5),
      "Game center should be displayed after login"
    );
    screen.click("Back.png");

    // Logout
    screen.click("Settings.png");
    screen.click("Logout.png");
    assertNotNull(
      screen.wait("LoginTitle.png"),
      "Login screen should be displayed after logout"
    );
  }
}
