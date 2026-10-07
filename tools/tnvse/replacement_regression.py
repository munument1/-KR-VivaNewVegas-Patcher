"""Compile real replacement/conversion functions with stubbed game lookups."""
from pathlib import Path
import argparse


def between(text, start, end):
    return text[text.index(start):text.index(end, text.index(start))]


def generate(source, output):
    font = source / 'tnvse/Src/font'
    encoding = between((font / 'encoding.cpp').read_text(),
                       '\tbool IsValidUTF8With3ByteMin', '\tstd::string WideToUTF8')
    dispatch = between((font / 'encoding.h').read_text(),
                       '\tinline bool ShouldConvertUTF8', '} // namespace fonthook')
    layout = between((font / 'font_text_layout.cpp').read_text(),
                     '\tstatic void EnsureTextScratchSize', '\tstruct PrepTextScratch')
    rich = between((font / 'font_manager.cpp').read_text(),
                   '\t\tbool TryAppendRichTextReplacement', '\t\tbool IsRichTextTextSegmentCollectTo')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(PREFIX + encoding + dispatch + layout + rich + TESTS, encoding='utf-8')


PREFIX = r'''
#define NOMINMAX
#include <Windows.h>
#include <string>
#include <vector>
#include <map>
#include <cstring>
#include <cassert>
#include <iostream>
#include <utility>
using UInt32 = unsigned int;
using UInt8 = unsigned char;
bool g_bEnableUTF8 = true;
UInt32 g_usingWinEncoding = 949;
bool IsEastAsianUiMode() { return true; }
bool hasGlyphs = true;
void* GetExtraGlyphs(int) { return hasGlyphs ? reinterpret_cast<void*>(1) : nullptr; }
bool HasRichTextExtraGlyphs() { return hasGlyphs; }
namespace text_safety { constexpr int kRetailReplacementNameMaxBytes = 255;
constexpr int kRetailReplacementOutputCapacity = 1024; }
struct Font { struct TextData { char cLineSep = '\n'; }; int iFontNum = 1;
std::vector<std::string> icons;
void AddTextIcon(const char* p) { icons.emplace_back(p); } };
struct FontEx : Font {};
struct FontManager { Font* pFont[1]; static FontManager* GetSingleton() { return nullptr; } };
std::map<std::string, std::string> gmst, replacements;
bool positive = true;
bool CopyLookup(const std::map<std::string, std::string>& lookup, const char* key, char* out) {
auto it = lookup.find(key); if (it == lookup.end()) return false;
strcpy_s(out, 1024, it->second.c_str()); return true; }
bool Interface_FindTextReplacementString(const char* key, char* out, UInt32, bool isPositive) {
positive = isPositive; return CopyLookup(replacements, key, out); }
bool Interface_TestConstantForGameSettings(const char* key, char* out) {
return CopyLookup(gmst, key, out); }
int GetRichTextCharType(UInt8 c) { return c == ' ' || c == '<' || c == '\n'; }
'''

TESTS = r'''
std::string Expand(const std::string& s, FontEx& font) {
std::vector<char> original(s.begin(), s.end()); original.resize(s.size() + 4);
std::vector<char> processed(s.size() + 4);
UInt32 size = s.size() + 4, len = 0, consumed = 0, sourceLen = s.size();
Font::TextData data;
ProcessEscapeSequences(original, processed, size, len, consumed, sourceLen, &font, &data);
return std::string(original.data()); }
int main() {
const std::string hangul = "확인";
const std::string cp949 = UTF8ToMultiByteStr(hangul, 949);
assert(cp949.size() == 4 && cp949 != hangul);
FontEx font;
gmst["sAccept"] = hangul;
replacements["kActivate"] = "사용";
assert(Expand("&sAccept;", font) == cp949);
assert(Expand("[&kActivate;] &sAccept;", font) == "[" + UTF8ToMultiByteStr("사용", 949) + "] " + cp949);
assert(Expand(cp949 + " &sAccept;", font) == cp949 + " " + cp949);
gmst["sAccept"] = cp949;
assert(Expand("&sAccept;", font) == cp949);
gmst["sAccept"] = "Accept";
assert(Expand("&sAccept;", font) == "Accept");
gmst["sAccept"] = hangul;
g_bEnableUTF8 = false;
assert(Expand("&sAccept;", font) == hangul);
g_bEnableUTF8 = true; hasGlyphs = false;
assert(Expand("&sAccept;", font) == hangul);
hasGlyphs = true;
replacements["icon"] = "X\\button.dds\\";
font.iFontNum = 7;
assert(Expand("&icon;", font) == std::string("X\x01"));
assert(font.icons.back() == "glow_button.dds\\");
assert(Expand("&-kActivate;", font) == UTF8ToMultiByteStr("사용", 949));
assert(!positive);
replacements["&sAccept;"] = hangul;
UInt32 index = 0; std::string out;
assert(TryAppendRichTextReplacement(nullptr, "&sAccept;", index, out));
assert(out == cp949 && index == 9);
replacements["&sAccept;"] = cp949;
index = 0; out.clear(); TryAppendRichTextReplacement(nullptr, "&sAccept;", index, out);
assert(out == cp949);
Font iconFont; FontManager manager; manager.pFont[0] = &iconFont;
replacements["&icon;"] = "\\button.dds";
index = 0; out.clear(); TryAppendRichTextReplacement(&manager, "&icon;", index, out);
assert(out == std::string(1, '\x01') && iconFont.icons.back() == "button.dds");
std::cout << "replacement regression: GMST, key prompts, mixed CP949, rich text, icon paths, flags passed\n";
}
'''

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    generate(args.source, args.output)
