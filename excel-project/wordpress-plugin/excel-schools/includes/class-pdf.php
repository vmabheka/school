<?php
/** Lightweight dependency-free PDF writer for downloadable portal documents. */
if (!defined('ABSPATH')) exit;

class ESM_PDF {
    private static function text($value) {
        $value = wp_strip_all_tags((string) $value);
        if (function_exists('iconv')) {
            $converted = @iconv('UTF-8', 'Windows-1252//TRANSLIT', $value);
            if ($converted !== false) $value = $converted;
        }
        $value = preg_replace('/[\x00-\x08\x0B\x0C\x0E-\x1F]/', '', $value);
        return str_replace(['\\', '(', ')'], ['\\\\', '\\(', '\\)'], $value);
    }

    private static function lines($title, $sections) {
        $lines = [['text' => $title, 'size' => 16]];
        $lines[] = ['text' => 'Generated: ' . gmdate('Y-m-d H:i') . ' UTC', 'size' => 9];
        $lines[] = ['text' => '', 'size' => 9];
        foreach ($sections as $section) {
            $lines[] = ['text' => $section['title'] ?? '', 'size' => 12];
            foreach (($section['rows'] ?? []) as $row) {
                $text = is_array($row) ? implode(' | ', array_map('strval', $row)) : (string) $row;
                $wrapped = explode("\n", wordwrap($text, 105, "\n", true));
                foreach ($wrapped as $part) $lines[] = ['text' => $part, 'size' => 9];
            }
            $lines[] = ['text' => '', 'size' => 9];
        }
        return $lines;
    }

    public static function download($filename, $title, $sections) {
        $chunks = array_chunk(self::lines($title, $sections), 50);
        if (!$chunks) $chunks = [[]];
        $objects = [];
        $objects[1] = '<< /Type /Catalog /Pages 2 0 R >>';
        $page_ids = [];
        $font_id = 3;
        $objects[$font_id] = '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>';

        foreach ($chunks as $index => $page_lines) {
            $page_id = 4 + ($index * 2);
            $content_id = $page_id + 1;
            $page_ids[] = $page_id . ' 0 R';
            $stream = "BT\n50 790 Td\n";
            $first = true;
            foreach ($page_lines as $line) {
                $size = max(8, min(18, (int) $line['size']));
                if (!$first) $stream .= "0 -14 Td\n";
                $stream .= "/F1 {$size} Tf\n(" . self::text($line['text']) . ") Tj\n";
                $first = false;
            }
            $stream .= "ET";
            $objects[$content_id] = "<< /Length " . strlen($stream) . " >>\nstream\n{$stream}\nendstream";
            $objects[$page_id] = "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 {$font_id} 0 R >> >> /Contents {$content_id} 0 R >>";
        }
        $objects[2] = '<< /Type /Pages /Count ' . count($page_ids) . ' /Kids [' . implode(' ', $page_ids) . '] >>';
        ksort($objects);

        $pdf = "%PDF-1.4\n";
        $offsets = [0];
        foreach ($objects as $id => $body) {
            $offsets[$id] = strlen($pdf);
            $pdf .= "{$id} 0 obj\n{$body}\nendobj\n";
        }
        $xref = strlen($pdf);
        $max_id = max(array_keys($objects));
        $pdf .= "xref\n0 " . ($max_id + 1) . "\n0000000000 65535 f \n";
        for ($id = 1; $id <= $max_id; $id++) {
            $pdf .= sprintf('%010d 00000 n ', $offsets[$id] ?? 0) . "\n";
        }
        $pdf .= "trailer\n<< /Size " . ($max_id + 1) . " /Root 1 0 R >>\nstartxref\n{$xref}\n%%EOF";

        nocache_headers();
        header('Content-Type: application/pdf');
        header('Content-Disposition: attachment; filename="' . sanitize_file_name($filename) . '"');
        header('Content-Length: ' . strlen($pdf));
        echo $pdf;
        exit;
    }
}
