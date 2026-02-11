export interface User {
  id: string;
  username: string;
  email: string;
  created_at: string;
}

export interface Source {
  title: string;
  body: string;
  href: string;
}

export interface Research {
  id: string;
  user_id: string;
  topic: string;
  latex_content: string;
  sources: Source[];
  model_used: string;
  search_queries: string[];
  pdf_object_key: string;
  tex_object_key: string;
  created_at: string;
}

export interface CreateResearchRequest {
  topic: string;
  model: string;
  depth: string;
  api_key: string;
}
