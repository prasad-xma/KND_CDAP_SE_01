import 'package:flutter/material.dart';
import 'en_en.dart';
import 'sl_sl.dart';

class LanguageController extends ChangeNotifier {
  LanguageController._internal();
  static final LanguageController instance = LanguageController._internal();

  bool _isEnglish = true;

  bool get isEnglish => _isEnglish;

  void setLanguage({required bool isEnglish}) {
    if (_isEnglish != isEnglish) {
      _isEnglish = isEnglish;
      notifyListeners();
    }
  }

  void toggleLanguage() {
    _isEnglish = !_isEnglish;
    notifyListeners();
  }

  String text(String key) {
    if (_isEnglish) {
      return enEnStrings[key] ?? key;
    } else {
      return slSlStrings[key] ?? enEnStrings[key] ?? key;
    }
  }
}

/// Global helper function to get translated text based on current global language
String tr(String key) => LanguageController.instance.text(key);
