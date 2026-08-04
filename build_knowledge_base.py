import re
import json
from discover_uni_ingestor import DiscoverUniIngestor
from competitor_scraper import CompetitorWebScraper

class DataNormalizationPipeline:
    @staticmethod
    def clean_text(text):
        """
        Deterministic string parsing using regular expressions.
        Strips whitespace anomalies, HTML breaks, and token artifacts.
        """
        if not text:
            return ""
        # Remove consecutive newline characters and tab layouts
        text = re.sub(r'[\r\n\t]+', ' ', text)
        # Collapse multiple whitespace areas into a uniform space string
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def merge_and_normalize(self):
        print("🚀 Executing Master Ingestion & Normalization Phase...")
        
        # Instantiate sub-modules
        quant_engine = DiscoverUniIngestor()
        qual_engine = CompetitorWebScraper()
        
        raw_quant = quant_engine.run_pipeline()
        final_unified_kb = []

        for uni_name, courses in raw_quant.items():
            for course_data in courses:
                # Scrape counterpart qualitative context if target URL profile exists
                target_url = qual_engine.target_urls.get(uni_name, "https://discoveruni.gov.uk/")
                scraped_details = qual_engine.scrape_course_details(uni_name, target_url)
                
                # Apply text transformations across unstructured nodes
                cleaned_y1 = self.clean_text(scraped_details.get("curriculum", {}).get("year_1", "Information Not Listed"))
                cleaned_y2 = self.clean_text(scraped_details.get("curriculum", {}).get("year_2", "Information Not Listed"))
                cleaned_y3 = self.clean_text(scraped_details.get("curriculum", {}).get("year_3", "Information Not Listed"))
                cleaned_placement = self.clean_text(scraped_details.get("placement_parameters", "Information Not Listed"))
                cleaned_facilities = self.clean_text(scraped_details.get("facilities_and_societies", "Information Not Listed"))

                # Structure everything into a clean JSON schema
                unified_entry = {
                    "university_name": uni_name,
                    "course_code": course_data["course_code"],
                    "ukprn": course_data["ukprn"],
                    "metrics": course_data["metrics"],
                    "knowledge_layers": {
                        "curriculum_year_1": cleaned_y1,
                        "curriculum_year_2": cleaned_y2,
                        "curriculum_year_3": cleaned_y3,
                        "industrial_placements": cleaned_placement,
                        "infrastructure_and_facilities": cleaned_facilities
                    },
                    "metadata_reference": {
                        "source_url": target_url,
                        "verification_layer": "HESA / Discover Uni / Institutional Web Scrape"
                    }
                }
                final_unified_kb.append(unified_entry)

        # Save the normalized dataset locally
        output_file = "clearing_knowledge_base.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(final_unified_kb, f, indent=4, ensure_ascii=False)
        
        print(f"📦 Production Pipeline Completed successfully! Data output to: {output_file}")

if __name__ == "__main__":
    pipeline = DataNormalizationPipeline()
    pipeline.merge_and_normalize()