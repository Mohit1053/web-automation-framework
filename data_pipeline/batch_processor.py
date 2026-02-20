"""Batch merging, validation, and log parsing utilities."""

import csv
import glob
import hashlib
import logging
import os
import random
import re
import shutil
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class ValidationReport:
    """Summary statistics from a CSV validation pass."""

    filepath: str
    total_rows: int
    unique_rows: int
    duplicate_rows: int
    avg_word_count: float
    min_word_count: int
    max_word_count: int
    column_counts: Dict[str, int]


class BatchMerger:
    """Merge multiple CSV files matching a glob pattern into one output file."""

    def merge(self, pattern: str, output_path: str) -> int:
        """
        Merge all CSV files matching *pattern* into *output_path*.

        Args:
            pattern: Glob pattern (e.g. ``"output_*.csv"``).
            output_path: Destination file path.

        Returns:
            Total number of data rows written (excluding headers).
        """
        files = sorted(glob.glob(pattern))
        if not files:
            logger.warning("No files matched pattern: %s", pattern)
            return 0

        total_rows = 0
        header_written = False

        with open(output_path, "w", newline="", encoding="utf-8") as out_fh:
            writer: Optional[csv.writer] = None
            for filepath in files:
                with open(filepath, "r", encoding="utf-8") as in_fh:
                    reader = csv.reader(in_fh)
                    header = next(reader, None)
                    if header is None:
                        continue
                    if not header_written:
                        writer = csv.writer(out_fh)
                        writer.writerow(header)
                        header_written = True
                    for row in reader:
                        if writer is not None:
                            writer.writerow(row)
                            total_rows += 1

        logger.info(
            "Merged %d files (%d rows) into %s", len(files), total_rows, output_path
        )
        return total_rows

    def validate(
        self, filepath: str, text_column: str, sample_size: int = 50_000
    ) -> ValidationReport:
        """
        Validate a CSV file for uniqueness and compute word-count statistics.

        For files exceeding *sample_size* rows the uniqueness check is
        performed on a random sample to keep memory bounded.

        Args:
            filepath: Path to the CSV file.
            text_column: Name of the column containing text to analyse.
            sample_size: Max rows to load for uniqueness sampling.

        Returns:
            A ``ValidationReport`` with summary statistics.
        """
        rows: List[Dict[str, str]] = []
        with open(filepath, "r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                rows.append(row)

        total = len(rows)
        if total > sample_size:
            logger.info(
                "Sampling %d of %d rows for uniqueness check.", sample_size, total
            )
            sample = random.sample(rows, sample_size)
        else:
            sample = rows

        seen: Set[str] = set()
        word_counts: List[int] = []
        for row in sample:
            text = row.get(text_column, "")
            digest = hashlib.md5(text.encode()).hexdigest()
            seen.add(digest)
            word_counts.append(len(text.split()))

        unique = len(seen)
        duplicates = len(sample) - unique
        avg_wc = sum(word_counts) / max(len(word_counts), 1)
        min_wc = min(word_counts) if word_counts else 0
        max_wc = max(word_counts) if word_counts else 0

        # Column non-null counts
        col_counts: Dict[str, int] = {}
        if rows:
            for col in rows[0].keys():
                col_counts[col] = sum(1 for r in sample if r.get(col))

        report = ValidationReport(
            filepath=filepath,
            total_rows=total,
            unique_rows=unique,
            duplicate_rows=duplicates,
            avg_word_count=round(avg_wc, 2),
            min_word_count=min_wc,
            max_word_count=max_wc,
            column_counts=col_counts,
        )
        logger.info(
            "Validation: %d total, %d unique, %d duplicates, avg words %.1f",
            total, unique, duplicates, avg_wc,
        )
        return report


class LogParser:
    """Parse structured log files to extract completion records."""

    def extract_completed(
        self,
        log_path: str,
        success_pattern: str = r"SUCCESS",
        id_pattern: str = r"id=([\w-]+)",
    ) -> List[str]:
        """
        Scan a log file and return IDs of successfully completed items.

        Args:
            log_path: Path to the log file.
            success_pattern: Regex that identifies success lines.
            id_pattern: Regex with one capture group for the item ID.

        Returns:
            List of extracted ID strings.
        """
        success_re = re.compile(success_pattern)
        id_re = re.compile(id_pattern)
        completed: List[str] = []

        with open(log_path, "r", encoding="utf-8") as fh:
            for line in fh:
                if success_re.search(line):
                    match = id_re.search(line)
                    if match:
                        completed.append(match.group(1))

        logger.info("Extracted %d completed IDs from %s", len(completed), log_path)
        return completed

    def cleanup_source(
        self,
        csv_path: str,
        completed_ids: List[str],
        id_column: str = "id",
    ) -> int:
        """
        Remove rows whose IDs appear in *completed_ids* from a CSV file.

        A backup of the original file is created before modification.

        Args:
            csv_path: Path to the source CSV file.
            completed_ids: IDs to remove.
            id_column: Name of the ID column.

        Returns:
            Number of rows removed.
        """
        backup_path = csv_path + ".bak"
        shutil.copy2(csv_path, backup_path)
        logger.info("Backup created at %s", backup_path)

        completed_set: Set[str] = set(completed_ids)
        kept_rows: List[List[str]] = []
        removed = 0

        with open(backup_path, "r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            fieldnames = reader.fieldnames or []
            for row in reader:
                if row.get(id_column, "") in completed_set:
                    removed += 1
                else:
                    kept_rows.append([row.get(c, "") for c in fieldnames])

        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(fieldnames)
            writer.writerows(kept_rows)

        logger.info(
            "Cleanup: removed %d rows, kept %d rows in %s",
            removed, len(kept_rows), csv_path,
        )
        return removed
