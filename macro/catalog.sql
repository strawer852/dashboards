-- macro catalog: US employment and labour-adjacent series.
-- Generated from the retired 0018_fred_seed.sql — curation preserved,
-- not retyped. Do not hand-edit; regenerate with gen_catalog.py.

BEGIN;

INSERT INTO macro_releases (release_id, name, agency, cadence, url) VALUES
  ('bls.employment_situation', 'Employment Situation', 'U.S. Bureau of Labor Statistics', 'monthly', 'https://www.bls.gov/news.release/empsit.toc.htm'),
  ('bls.jolts', 'Job Openings and Labor Turnover Survey', 'U.S. Bureau of Labor Statistics', 'monthly', 'https://www.bls.gov/news.release/jolts.toc.htm'),
  ('eta.claims', 'Unemployment Insurance Weekly Claims Report', 'U.S. Employment and Training Administration', 'weekly', 'https://www.dol.gov/ui/data.pdf'),
  ('bls.eci', 'Employment Cost Index', 'U.S. Bureau of Labor Statistics', 'quarterly', 'https://www.bls.gov/news.release/eci.toc.htm'),
  ('bls.productivity', 'Productivity and Costs', 'U.S. Bureau of Labor Statistics', 'quarterly', 'https://www.bls.gov/news.release/prod2.toc.htm'),
  ('frb.wage_tracker', 'Atlanta Fed Wage Growth Tracker', 'Federal Reserve Bank of Atlanta', 'monthly', 'https://www.atlantafed.org/chcs/wage-growth-tracker')
ON CONFLICT (release_id) DO NOTHING;

INSERT INTO macro_series_meta (series_id, source, title, frequency, country, category, importance, seasonal_adjustment, companion_series_id, validation_mode, originator, dataset, source_url, unit, release_id, vintage_mode) VALUES
  ('ECIALLCIV', 'fred', 'Employment Cost Index: Total compensation: All Civilian', 'Q', 'US', 'prices', 8, 'SA', NULL, 'zscore', 'U.S. Bureau of Labor Statistics', 'Employment Cost Index', 'https://fred.stlouisfed.org/series/ECIALLCIV', NULL, 'bls.eci', 'from_row'),
  ('ECIWAG', 'fred', 'Employment Cost Index: Wages and Salaries: Private Industry Workers', 'Q', 'US', 'prices', 8, 'SA', NULL, 'zscore', 'U.S. Bureau of Labor Statistics', 'Employment Cost Index', 'https://fred.stlouisfed.org/series/ECIWAG', NULL, 'bls.eci', 'from_row'),
  ('PAYEMS', 'fred', 'All Employees, Total Nonfarm', 'M', 'US', 'employment', 10, 'SA', 'PAYNSA', 'zscore', 'U.S. Bureau of Labor Statistics', 'Employment Situation', 'https://fred.stlouisfed.org/series/PAYEMS', NULL, 'bls.employment_situation', 'from_row'),
  ('UNRATE', 'fred', 'Unemployment Rate', 'M', 'US', 'employment', 10, 'SA', 'UNRATENSA', 'zscore', 'U.S. Bureau of Labor Statistics', 'Employment Situation', 'https://fred.stlouisfed.org/series/UNRATE', NULL, 'bls.employment_situation', 'from_row'),
  ('CES0500000003', 'fred', 'Average Hourly Earnings of All Employees, Total Private', 'M', 'US', 'employment', 8, 'SA', 'CEU0500000003', 'zscore', 'U.S. Bureau of Labor Statistics', 'Employment Situation', 'https://fred.stlouisfed.org/series/CES0500000003', NULL, 'bls.employment_situation', 'from_row'),
  ('CIVPART', 'fred', 'Labor Force Participation Rate', 'M', 'US', 'employment', 8, 'SA', 'LNU01300000', 'zscore', 'U.S. Bureau of Labor Statistics', 'Employment Situation', 'https://fred.stlouisfed.org/series/CIVPART', NULL, 'bls.employment_situation', 'from_row'),
  ('USPRIV', 'fred', 'All Employees, Total Private', 'M', 'US', 'employment', 8, 'SA', NULL, 'zscore', 'U.S. Bureau of Labor Statistics', 'Employment Situation', 'https://fred.stlouisfed.org/series/USPRIV', NULL, 'bls.employment_situation', 'from_row'),
  ('AHETPI', 'fred', 'Average Hourly Earnings of Production and Nonsupervisory Employees, Total Private', 'M', 'US', 'employment', 7, 'SA', 'CEU0500000008', 'zscore', 'U.S. Bureau of Labor Statistics', 'Employment Situation', 'https://fred.stlouisfed.org/series/AHETPI', NULL, 'bls.employment_situation', 'from_row'),
  ('EMRATIO', 'fred', 'Employment-Population Ratio', 'M', 'US', 'employment', 7, 'SA', 'LNU02300000', 'zscore', 'U.S. Bureau of Labor Statistics', 'Employment Situation', 'https://fred.stlouisfed.org/series/EMRATIO', NULL, 'bls.employment_situation', 'from_row'),
  ('PAYNSA', 'fred', 'All Employees, Total Nonfarm', 'M', 'US', 'employment', 7, 'NSA', 'PAYEMS', 'zscore', 'U.S. Bureau of Labor Statistics', 'Employment Situation', 'https://fred.stlouisfed.org/series/PAYNSA', NULL, 'bls.employment_situation', 'from_row'),
  ('U6RATE', 'fred', 'Total Unemployed, Plus All Persons Marginally Attached to the Labor Force, Plus Total Employed Part Time for Economic Reasons, as a Percent of the Civilian Labor Force Plus All Persons Marginally Attached to the Labor Force (U-6)', 'M', 'US', 'employment', 7, 'SA', 'U6RATENSA', 'zscore', 'U.S. Bureau of Labor Statistics', 'Employment Situation', 'https://fred.stlouisfed.org/series/U6RATE', NULL, 'bls.employment_situation', 'from_row'),
  ('UNRATENSA', 'fred', 'Unemployment Rate', 'M', 'US', 'employment', 7, 'NSA', 'UNRATE', 'zscore', 'U.S. Bureau of Labor Statistics', 'Employment Situation', 'https://fred.stlouisfed.org/series/UNRATENSA', NULL, 'bls.employment_situation', 'from_row'),
  ('CEU0500000003', 'fred', 'Average Hourly Earnings of All Employees, Total Private', 'M', 'US', 'employment', 6, 'NSA', 'CES0500000003', 'zscore', 'U.S. Bureau of Labor Statistics', 'Employment Situation', 'https://fred.stlouisfed.org/series/CEU0500000003', NULL, 'bls.employment_situation', 'from_row'),
  ('LNU01300000', 'fred', 'Labor Force Participation Rate', 'M', 'US', 'employment', 6, 'NSA', 'CIVPART', 'zscore', 'U.S. Bureau of Labor Statistics', 'Employment Situation', 'https://fred.stlouisfed.org/series/LNU01300000', NULL, 'bls.employment_situation', 'from_row'),
  ('MANEMP', 'fred', 'All Employees, Manufacturing', 'M', 'US', 'employment', 6, 'SA', NULL, 'zscore', 'U.S. Bureau of Labor Statistics', 'Employment Situation', 'https://fred.stlouisfed.org/series/MANEMP', NULL, 'bls.employment_situation', 'from_row'),
  ('AWHAETP', 'fred', 'Average Weekly Hours of All Employees, Total Private', 'M', 'US', 'employment', 5, 'SA', NULL, 'zscore', 'U.S. Bureau of Labor Statistics', 'Employment Situation', 'https://fred.stlouisfed.org/series/AWHAETP', NULL, 'bls.employment_situation', 'from_row'),
  ('CEU0500000008', 'fred', 'Average Hourly Earnings of Production and Nonsupervisory Employees, Total Private', 'M', 'US', 'employment', 5, 'NSA', 'AHETPI', 'zscore', 'U.S. Bureau of Labor Statistics', 'Employment Situation', 'https://fred.stlouisfed.org/series/CEU0500000008', NULL, 'bls.employment_situation', 'from_row'),
  ('LNU02300000', 'fred', 'Employment-Population Ratio', 'M', 'US', 'employment', 5, 'NSA', 'EMRATIO', 'zscore', 'U.S. Bureau of Labor Statistics', 'Employment Situation', 'https://fred.stlouisfed.org/series/LNU02300000', NULL, 'bls.employment_situation', 'from_row'),
  ('U6RATENSA', 'fred', 'Total Unemployed, Plus All Persons Marginally Attached to the Labor Force, Plus Total Employed Part Time for Economic Reasons, as a Percent of the Civilian Labor Force Plus All Persons Marginally Attached to the Labor Force (U-6)', 'M', 'US', 'employment', 5, 'NSA', 'U6RATE', 'zscore', 'U.S. Bureau of Labor Statistics', 'Employment Situation', 'https://fred.stlouisfed.org/series/U6RATENSA', NULL, 'bls.employment_situation', 'from_row'),
  ('JTSJOL', 'fred', 'Job Openings: Total Nonfarm', 'M', 'US', 'employment', 9, 'SA', 'JTUJOL', 'zscore', 'U.S. Bureau of Labor Statistics', 'Job Openings and Labor Turnover Survey', 'https://fred.stlouisfed.org/series/JTSJOL', NULL, 'bls.jolts', 'from_row'),
  ('JTSQUL', 'fred', 'Quits: Total Nonfarm', 'M', 'US', 'employment', 7, 'SA', 'JTUQUL', 'zscore', 'U.S. Bureau of Labor Statistics', 'Job Openings and Labor Turnover Survey', 'https://fred.stlouisfed.org/series/JTSQUL', NULL, 'bls.jolts', 'from_row'),
  ('JTSHIL', 'fred', 'Hires: Total Nonfarm', 'M', 'US', 'employment', 6, 'SA', NULL, 'zscore', 'U.S. Bureau of Labor Statistics', 'Job Openings and Labor Turnover Survey', 'https://fred.stlouisfed.org/series/JTSHIL', NULL, 'bls.jolts', 'from_row'),
  ('JTSLDL', 'fred', 'Layoffs and Discharges: Total Nonfarm', 'M', 'US', 'employment', 6, 'SA', NULL, 'zscore', 'U.S. Bureau of Labor Statistics', 'Job Openings and Labor Turnover Survey', 'https://fred.stlouisfed.org/series/JTSLDL', NULL, 'bls.jolts', 'from_row'),
  ('JTUJOL', 'fred', 'Job Openings: Total Nonfarm', 'M', 'US', 'employment', 6, 'NSA', 'JTSJOL', 'zscore', 'U.S. Bureau of Labor Statistics', 'Job Openings and Labor Turnover Survey', 'https://fred.stlouisfed.org/series/JTUJOL', NULL, 'bls.jolts', 'from_row'),
  ('JTUQUL', 'fred', 'Quits: Total Nonfarm', 'M', 'US', 'employment', 5, 'NSA', 'JTSQUL', 'zscore', 'U.S. Bureau of Labor Statistics', 'Job Openings and Labor Turnover Survey', 'https://fred.stlouisfed.org/series/JTUQUL', NULL, 'bls.jolts', 'from_row'),
  ('OPHNFB', 'fred', 'Nonfarm Business Sector: Labor Productivity (Output per Hour) for All Workers', 'Q', 'US', 'prices', 6, 'SA', NULL, 'zscore', 'U.S. Bureau of Labor Statistics', 'Productivity and Costs', 'https://fred.stlouisfed.org/series/OPHNFB', NULL, 'bls.productivity', 'from_row'),
  ('ULCNFB', 'fred', 'Nonfarm Business Sector: Unit Labor Costs for All Workers', 'Q', 'US', 'prices', 6, 'SA', NULL, 'zscore', 'U.S. Bureau of Labor Statistics', 'Productivity and Costs', 'https://fred.stlouisfed.org/series/ULCNFB', NULL, 'bls.productivity', 'from_row'),
  ('ICSA', 'fred', 'Initial Claims', 'W', 'US', 'employment', 9, 'SA', 'ICNSA', 'zscore', 'U.S. Employment and Training Administration', 'Unemployment Insurance Weekly Claims Report', 'https://fred.stlouisfed.org/series/ICSA', NULL, 'eta.claims', 'from_row'),
  ('CCSA', 'fred', 'Continued Claims (Insured Unemployment)', 'W', 'US', 'employment', 7, 'SA', 'CCNSA', 'zscore', 'U.S. Employment and Training Administration', 'Unemployment Insurance Weekly Claims Report', 'https://fred.stlouisfed.org/series/CCSA', NULL, 'eta.claims', 'from_row'),
  ('IC4WSA', 'fred', '4-Week Moving Average of Initial Claims', 'W', 'US', 'employment', 7, 'SA', NULL, 'zscore', 'U.S. Employment and Training Administration', 'Unemployment Insurance Weekly Claims Report', 'https://fred.stlouisfed.org/series/IC4WSA', NULL, 'eta.claims', 'from_row'),
  ('ICNSA', 'fred', 'Initial Claims', 'W', 'US', 'employment', 6, 'NSA', 'ICSA', 'zscore', 'U.S. Employment and Training Administration', 'Unemployment Insurance Weekly Claims Report', 'https://fred.stlouisfed.org/series/ICNSA', NULL, 'eta.claims', 'from_row'),
  ('CCNSA', 'fred', 'Continued Claims (Insured Unemployment)', 'W', 'US', 'employment', 5, 'NSA', 'CCSA', 'zscore', 'U.S. Employment and Training Administration', 'Unemployment Insurance Weekly Claims Report', 'https://fred.stlouisfed.org/series/CCNSA', NULL, 'eta.claims', 'from_row'),
  ('FRBATLWGT3MMAUMHWGO', 'fred', '3-Month Moving Average of Unweighted Median Hourly Wage Growth: Overall', 'M', 'US', 'prices', 7, 'N/A', NULL, 'zscore', 'Federal Reserve Bank of Atlanta', 'Wage Growth Tracker', 'https://fred.stlouisfed.org/series/FRBATLWGT3MMAUMHWGO', NULL, 'frb.wage_tracker', 'fetch_date')
ON CONFLICT (series_id) DO UPDATE SET
  title = EXCLUDED.title, importance = EXCLUDED.importance,
  companion_series_id = EXCLUDED.companion_series_id,
  dataset = EXCLUDED.dataset, release_id = EXCLUDED.release_id,
  vintage_mode = EXCLUDED.vintage_mode;

COMMIT;
