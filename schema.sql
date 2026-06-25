--
-- PostgreSQL database dump
--

\restrict JCwvE3aVn08qsFWrOW1Gm7HwK0zId5KyZCJJ3JWRS776HNfRcxf1Bv7kegEbfci

-- Dumped from database version 15.18
-- Dumped by pg_dump version 15.18

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: applications; Type: TABLE; Schema: public; Owner: postgres_admin
--

CREATE TABLE public.applications (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    draft_id uuid,
    sent_at timestamp with time zone,
    status text DEFAULT 'sent'::text
);


ALTER TABLE public.applications OWNER TO postgres_admin;

--
-- Name: email_drafts; Type: TABLE; Schema: public; Owner: postgres_admin
--

CREATE TABLE public.email_drafts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    job_id uuid,
    poc_name text,
    poc_email text,
    subject text,
    body text,
    status text DEFAULT 'pending'::text,
    feedback text,
    version integer DEFAULT 1,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.email_drafts OWNER TO postgres_admin;

--
-- Name: jobs; Type: TABLE; Schema: public; Owner: postgres_admin
--

CREATE TABLE public.jobs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    resume_id uuid,
    title text,
    company text,
    location text,
    jd_url text,
    jd_text text,
    source text,
    match_score double precision,
    found_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.jobs OWNER TO postgres_admin;

--
-- Name: resumes; Type: TABLE; Schema: public; Owner: postgres_admin
--

CREATE TABLE public.resumes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid,
    filename text,
    preferences jsonb,
    uploaded_at timestamp with time zone DEFAULT now(),
    experience jsonb,
    skills jsonb,
    education jsonb
);


ALTER TABLE public.resumes OWNER TO postgres_admin;

--
-- Name: users; Type: TABLE; Schema: public; Owner: postgres_admin
--

CREATE TABLE public.users (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text,
    email text NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.users OWNER TO postgres_admin;

--
-- Name: applications applications_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres_admin
--

ALTER TABLE ONLY public.applications
    ADD CONSTRAINT applications_pkey PRIMARY KEY (id);


--
-- Name: email_drafts email_drafts_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres_admin
--

ALTER TABLE ONLY public.email_drafts
    ADD CONSTRAINT email_drafts_pkey PRIMARY KEY (id);


--
-- Name: jobs jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres_admin
--

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT jobs_pkey PRIMARY KEY (id);


--
-- Name: resumes resumes_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres_admin
--

ALTER TABLE ONLY public.resumes
    ADD CONSTRAINT resumes_pkey PRIMARY KEY (id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: postgres_admin
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres_admin
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: applications applications_draft_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres_admin
--

ALTER TABLE ONLY public.applications
    ADD CONSTRAINT applications_draft_id_fkey FOREIGN KEY (draft_id) REFERENCES public.email_drafts(id);


--
-- Name: email_drafts email_drafts_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres_admin
--

ALTER TABLE ONLY public.email_drafts
    ADD CONSTRAINT email_drafts_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.jobs(id);


--
-- Name: jobs jobs_resume_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres_admin
--

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT jobs_resume_id_fkey FOREIGN KEY (resume_id) REFERENCES public.resumes(id);


--
-- Name: resumes resumes_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres_admin
--

ALTER TABLE ONLY public.resumes
    ADD CONSTRAINT resumes_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- PostgreSQL database dump complete
--

\unrestrict JCwvE3aVn08qsFWrOW1Gm7HwK0zId5KyZCJJ3JWRS776HNfRcxf1Bv7kegEbfci

