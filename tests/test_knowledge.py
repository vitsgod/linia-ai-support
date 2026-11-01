from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.knowledge import load_chunks


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)

    def write(self, name, text):
        (self.directory / name).write_text(text, encoding='utf-8')

    def test_sections_preserve_document_context_without_mixing(self):
        self.write('wifi.md', '# Wi-Fi\n\nУчебная инструкция.\n\n## Условия\nСеть не видна.\n\n## Проверки\nВключить Wi-Fi.\n')
        self.write('cable.md', '# Кабель\n\n## Проверки\nОсмотреть разъём.\n')
        chunks = load_chunks(self.directory)
        self.assertEqual(len(chunks), 3)
        wifi = [chunk for chunk in chunks if chunk.document_id == 'wifi']
        self.assertEqual([chunk.section for chunk in wifi], ['Условия', 'Проверки'])
        self.assertEqual(wifi[0].content, 'Сеть не видна.')
        self.assertNotIn('Включить', wifi[0].content)
        self.assertIn('Wi-Fi', wifi[0].text)
        self.assertIn('Условия', wifi[0].text)
        self.assertIn('Сеть не видна.', wifi[0].text)
        self.assertEqual(wifi[0].source, 'wifi.md')
        self.assertEqual(len({chunk.id for chunk in chunks}), 3)

    def test_empty_directory_fails_explicitly(self):
        with self.assertRaisesRegex(ValueError, 'Нет'):
            load_chunks(self.directory)

    def test_missing_title_or_sections_are_rejected(self):
        for text in ['## Раздел\nТекст', '# Название\nНет разделов']:
            with self.subTest(text=text):
                self.write('bad.md', text)
                with self.assertRaises(ValueError):
                    load_chunks(self.directory)

    def test_empty_and_repeated_sections_are_rejected(self):
        for text in ['# Название\n## Пусто\n\n', '# Название\n## Раздел\nОдин\n## Раздел\nДва']:
            with self.subTest(text=text):
                self.write('bad.md', text)
                with self.assertRaises(ValueError):
                    load_chunks(self.directory)

    def test_oversized_section_is_not_silently_truncated(self):
        self.write('large.md', '# Название\n## Раздел\n' + 'я' * 1601)
        with self.assertRaisesRegex(ValueError, '1600'):
            load_chunks(self.directory)

    def test_nested_heading_remains_inside_section(self):
        self.write('wifi.md', '# Wi-Fi\n## Проверки\nТекст\n### Индикаторы\nУточнить модель.')
        chunks = load_chunks(self.directory)
        self.assertEqual(len(chunks), 1)
        self.assertIn('### Индикаторы', chunks[0].content)


if __name__ == '__main__':
    unittest.main()
