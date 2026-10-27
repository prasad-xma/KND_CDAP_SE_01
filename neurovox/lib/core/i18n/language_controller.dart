import 'package:flutter/material.dart';
import 'en_en.dart';
import 'sl_sl.dart';
import 'ta_ta.dart';

enum AppLanguage { english, sinhala, tamil }

class LanguageController extends ChangeNotifier {
  LanguageController._internal();
  static final LanguageController instance = LanguageController._internal();

  AppLanguage _language = AppLanguage.english;

  AppLanguage get language => _language;

  bool get isEnglish => _language == AppLanguage.english;

  void setAppLanguage(AppLanguage language) {
    if (_language != language) {
      _language = language;
      notifyListeners();
    }
  }

  void setLanguage({required bool isEnglish}) {
    setAppLanguage(isEnglish ? AppLanguage.english : AppLanguage.sinhala);
  }

  void toggleLanguage() {
    setAppLanguage(_language == AppLanguage.english ? AppLanguage.sinhala : AppLanguage.english);
  }

  String text(String key) {
    switch (_language) {
      case AppLanguage.sinhala:
        return slSlStrings[key] ?? enEnStrings[key] ?? key;
      case AppLanguage.tamil:
        return taTaStrings[key] ?? enEnStrings[key] ?? key;
      case AppLanguage.english:
        return enEnStrings[key] ?? key;
    }
  }
}

/// Global helper function to get translated text based on current global language
String tr(String key) => LanguageController.instance.text(key);
