"""Package association contracts from upstream Gitea v1.24.7 and v28.2.0.

See docs/image-releases.md for the exact schema, conversion, middleware,
permission and link-service sources. No test contacts a live service.
"""

import copy
import json
import time
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from test_build_all import PROJECT, ReleaseFixture, data, ports


class PackagePublicationTests(ReleaseFixture):
  def package(self, repository=None):
    return {"versions": ["older"], "repository": repository}

  def test_both_characterized_server_contracts_publish(self):
    for version in ("1.24.7", "28.2.0"):
      with self.subTest(version=version):
        self.make_fixture("2.4.6")
        state = self.state()
        state["server_version"] = {"version": version}
        if version == "1.24.7":
          # This schema genuinely has no User.type field.
          for key in ("principal", "namespace"):
            state[key].pop("type")
          state["repository"]["owner"].pop("type")
        self.store(state)
        self.assertEqual(state["packages"], {})
        self.assertEqual(state["local_images"], {})
        self.assert_success(self.run_script())
        state = self.state()
        self.assertEqual([v for k, v in state["effects"] if k == "build"], ["base", "npm"])
        self.assertEqual([v for k, v in state["effects"] if k == "link"], ["base", "npm"])
        owner_reads = [call[-1] for call in state["calls"] if call[0] == "curl" and
                       urlsplit(call[-1]).path == "/api/v1/packages/dev"]
        self.assertEqual(bool(owner_reads), version == "28.2.0")
        for name in ("base", "npm"):
          self.assertEqual(state["packages"][name]["repository"], state["repository"])
          self.assertIn(self.tag, state["packages"][name]["versions"])
          self.assertIn("latest", state["packages"][name]["versions"])
        self.assertIn(self.tag, state["tags"])
        self.assertEqual(state["release"]["tag_name"], self.tag)
        self.change(effects=[], calls=[])
        self.assert_success(self.run_script())
        self.assertEqual(self.state()["effects"], [])

  def test_one_missing_package_publishes_with_existing_linked_or_unlinked_package(self):
    for linked in (False, True):
      with self.subTest(linked=linked):
        self.make_fixture("2.4.6")
        repository = self.state()["repository"] if linked else None
        self.change(packages={"base": self.package(repository)})
        self.assert_success(self.run_script())
        effects = self.state()["effects"]
        self.assertEqual([v for k, v in effects if k == "build"], ["base", "npm"])
        self.assertEqual([v for k, v in effects if k == "link"], ["npm"] if linked else ["base", "npm"])

  def test_existing_unlinked_and_correct_packages(self):
    self.change(packages={"base": self.package(), "npm": self.package(self.state()["repository"])})
    self.assert_success(self.run_script())
    self.assertEqual([v for k, v in self.state()["effects"] if k == "link"], ["base"])

  def test_delegate_hidden_null_refuses_before_any_writes(self):
    state = self.state()
    foreign = copy.deepcopy(state["repository"])
    foreign.update(id=20, full_name="dev/private-other")
    state["packages"] = {"base": self.package(foreign)}
    state["principal"].update(id=8, login="delegate", is_admin=True)
    state["hide_links"] = True
    self.store(state)
    self.assert_refused_without_writes(self.run_script())
    self.assertFalse(any("/link/" in call[-1] for call in self.state()["calls"]))
    self.assertEqual(self.state()["packages"]["base"]["repository"], foreign)

  def test_foreign_association_refuses_before_any_writes(self):
    foreign = copy.deepcopy(self.state()["repository"])
    foreign.update(id=20, full_name="dev/other")
    self.change(packages={"npm": self.package(foreign)})
    self.assert_refused_without_writes(self.run_script())

  def test_package_http_errors_and_unsupported_versions_refuse_without_writes(self):
    baseline = self.state()
    cases = []
    for code in (401, 403, 404, 302, 500):
      responses = {"/api/v1/packages/dev/container/base": {
        "code": code, "body": {"message": "synthetic-http-body-secret"}}}
      # A failed named read alone no longer decides absence. Its independent
      # owner inventory must also be unavailable for this arbitrary-404 refusal.
      if code == 404:
        responses["/api/v1/packages/dev"] = {"code": 404, "body": {}}
      cases.append({"responses": responses})
    cases += [{"server_version": {"version": "28.2.1"}},
              {"server_version": {"version": "28.2.0-custom"}},
              {"server_version": {"version": "28.2.0+dev"}},
              {"responses": {"/api/v1/version": {"code": 404, "body": {}}}},
              {"responses": {"/api/v1/packages/dev/container/npm": {"transport_failure": True}}}]
    for case in cases:
      with self.subTest(case=case):
        self.store(copy.deepcopy(baseline) | case)
        result = self.run_script()
        self.assert_refused_without_writes(result)
        for response in case.get("responses", {}).values():
          if "code" in response:
            code = response["code"]
            self.assertRegex(result.stderr, rf"HTTP(?: status:)? {code}\b")
        self.assertNotIn("test-secret", result.stdout + result.stderr)
        self.assertNotIn("synthetic-http-body-secret", result.stdout + result.stderr)

  def test_oversized_package_response_refuses_without_writes(self):
    self.change(responses={"/api/v1/packages/dev/container/base": {"raw": "x" * (ports.API_LIMIT + 1)}})
    result = self.run_script()
    self.assert_refused_without_writes(result)
    self.assertIn("exceeds byte limit", result.stderr)
    self.assertNotIn("test-secret", result.stdout + result.stderr)

  def test_owner_inventory_failures_stop_first_publication_without_writes(self):
    baseline = self.state()
    responses = [{"code": code, "body": {"message": "synthetic-owner-secret"}}
                 for code in (401, 403, 404, 500)]
    responses += [{"transport_failure": True}, {"raw": "synthetic-owner-secret"},
                  {"body": {}}, {"body": None}, {"raw": "x" * (ports.API_LIMIT + 1)}]
    for response in responses:
      with self.subTest(response=list(response)):
        self.store(copy.deepcopy(baseline) | {"responses": {"/api/v1/packages/dev": response}})
        result = self.run_script()
        self.assert_refused_without_writes(result)
        if "code" in response:
          self.assertRegex(result.stderr, rf"HTTP(?: status:)? {response['code']}\b")
        for secret in ("test-secret", "synthetic-owner-secret", str(self.token)):
          self.assertNotIn(secret, result.stdout + result.stderr)

  def test_named_404_with_existing_owner_record_refuses_before_writes(self):
    self.change(packages={"base": self.package()}, responses={
      "/api/v1/packages/dev/container/base": {"code": 404, "body": {}}})
    result = self.run_script()
    self.assert_refused_without_writes(result)
    self.assertIn("owner inventory contains it", result.stderr)

  def test_owner_search_near_matches_are_not_mutated(self):
    foreign = copy.deepcopy(self.state()["repository"])
    foreign.update(id=20, full_name="dev/other")
    neighboring = {"base-tools": self.package(foreign), "npm-tools": self.package()}
    self.change(packages=neighboring)
    self.assert_success(self.run_script())
    for name, value in neighboring.items():
      self.assertEqual(self.state()["packages"][name], value)
    self.assertEqual([v for k, v in self.state()["effects"] if k == "link"], ["base", "npm"])

  def test_failed_second_link_retry_reuses_images_and_first_link(self):
    self.change(fail="link:npm")
    result = self.run_script()
    self.assertNotEqual(result.returncode, 0)
    state = self.state()
    self.assertEqual([v for k, v in state["effects"] if k == "link"], ["base"])
    self.assertFalse(state["tags"])
    self.assertIsNone(state["release"])
    self.assertIn('"base":19', result.stderr)
    state.pop("fail")
    state["effects"] = []
    self.store(state)
    self.assert_success(self.run_script())
    self.assertFalse(any(k == "build" for k, _ in self.state()["effects"]))
    self.assertEqual([v for k, v in self.state()["effects"] if k == "link"], ["npm"])

  def test_lost_link_response_reconciles_once(self):
    self.change(lose_response="link")
    self.assert_success(self.run_script())
    self.assertEqual([v for k, v in self.state()["effects"] if k == "link"], ["base", "npm"])

  def test_lost_link_response_without_exact_evidence_stops(self):
    # The fake applies the link, loses its response, then hides post-write reads.
    self.change(lose_response="link", after_link={"responses": {
      "/api/v1/packages/dev/container/base": {"code": 404, "body": []}}})
    self.assertNotEqual(self.run_script().returncode, 0)
    state = self.state()
    self.assertFalse(state["tags"])
    self.assertIsNone(state["release"])
    self.assertEqual([v for k, v in state["effects"] if k == "link"], ["base"])

  def test_authority_and_settings_drift_after_staging_prevent_link(self):
    baseline = self.state()
    repo = copy.deepcopy(baseline["repository"])
    repo["has_packages"] = False
    principal = copy.deepcopy(baseline["principal"])
    principal["id"] = 8
    for drift in ({"repository": repo}, {"principal": principal}):
      with self.subTest(drift=drift):
        self.store(copy.deepcopy(baseline) | {"after_staging": drift})
        self.assertNotEqual(self.run_script().returncode, 0)
        state = self.state()
        self.assertFalse(any(k in ("link", "tag", "post") for k, _ in state["effects"]))

  def test_packages_disappearing_after_staging_cannot_be_linked(self):
    self.change(after_staging={"packages": {}})
    result = self.run_script()
    self.assertNotEqual(result.returncode, 0)
    self.assertIn("Staged package disappeared", result.stderr)
    self.assertFalse(any(k in ("link", "tag", "promote", "post") for k, _ in self.state()["effects"]))

  def test_association_drift_after_first_link_prevents_tag(self):
    self.change(after_link={"hide_links": True})
    self.assertNotEqual(self.run_script().returncode, 0)
    self.assertFalse(self.state()["tags"])

  def test_completed_retry_missing_or_foreign_association_never_repairs(self):
    self.assert_success(self.run_script())
    baseline = self.state()
    foreign = copy.deepcopy(baseline["repository"])
    foreign.update(id=20, full_name="dev/other")
    for association in (None, foreign):
      with self.subTest(association=association):
        state = copy.deepcopy(baseline)
        state["packages"]["base"]["repository"] = association
        state["effects"], state["calls"] = [], []
        self.store(state)
        self.assert_refused_without_writes(self.run_script())

  def test_internal_only_already_linked_record_is_not_reassigned(self):
    foreign = copy.deepcopy(self.state()["repository"])
    foreign.update(id=20, full_name="dev/other")
    # Empty non-internal listing at startup, but the service still knows the link.
    self.change(packages={"base": {"versions": [], "repository": foreign}})
    self.assertNotEqual(self.run_script().returncode, 0)
    state = self.state()
    self.assertFalse(state["tags"])
    self.assertFalse(any(k == "link" for k, _ in state["effects"]))
    self.assertEqual(state["packages"]["base"]["repository"], foreign)

  def test_excluded_images_remain_manual_and_do_not_block_either_mode(self):
    retained = ["android", "tauri", "switchboard"]
    for name in retained:
      self.assertTrue((PROJECT / "Dockerfile" / (name + ".Dockerfile")).is_file())
      (self.project / "Dockerfile" / (name + ".Dockerfile")).unlink()
    self.git("add", "Dockerfile")
    self.git("commit", "-m", "Remove excluded inputs from test fixture only")
    excluded = ("my-base", "npm-non-root", "android-dev", "android", "tauri-dev", "switchboard")
    manifests = {"git.lan/dev/" + name + "/" + self.tag: {"foreign": True} for name in excluded}
    self.change(commit=self.git("rev-parse", "HEAD").strip(), manifests=manifests)
    self.assert_success(self.run_script("--validate"))
    self.assert_success(self.run_script("--build-only"))
    self.change(effects=[], calls=[])
    self.assert_success(self.run_script())
    state = self.state()
    for key, value in manifests.items():
      self.assertEqual(state["manifests"][key], value)
    calls = json.dumps(state["calls"])
    for name in excluded:
      self.assertNotIn("/" + name + "/", calls)
    oid = state["tags"][self.tag]
    raw = self.git("cat-file", "tag", oid).split(data.MARKER.decode(), 1)[1]
    identity = json.loads(raw)
    self.assertEqual(set(identity["digests"]), {"base", "npm"})
    self.assertEqual(set(identity["predecessors"]), {"base", "npm"})


class PackageEvidenceTests(ReleaseFixture):
  def check(self, records=None, responses=None, complete=False, repeated=False, owner_records=None):
    work = self.root / ("evidence-" + str(len(list(self.root.glob("evidence-*")))))
    work.mkdir()
    (work / "login").write_text("dev")
    ports.write(work / "state.json", {"links": {}, "packages_ready": False})
    state = self.state()
    values = {"/api/v1/version": state["server_version"], "/api/v1/user": state["principal"],
              "/api/v1/users/dev": state["namespace"], "/api/v1/repos/dev/dev-docker": state["repository"]}
    def http(_work, method, url, **kwargs):
      self.assertEqual(method, "GET")
      parsed = urlsplit(url)
      query = parse_qs(parsed.query)
      page = int(query.get("page", ["1"])[0])
      if responses and (parsed.path, page) in responses:
        code, body = responses[(parsed.path, page)]
      elif responses and parsed.path in responses:
        code, body = responses[parsed.path]
      elif parsed.path in values:
        code, body = 200, values[parsed.path]
      elif parsed.path == "/api/v1/packages/dev":
        self.assertEqual(query["type"], ["container"])
        self.assertEqual(query["limit"], ["100"])
        self.assertIn(query["q"][0], ("base", "npm"))
        items = owner_records or []
        code, body = 200, items[:100] if repeated else items[(page - 1) * 100:page * 100]
      else:
        name = parsed.path.rsplit("/", 1)[-1]
        items = (records or {}).get(name, [])
        code, body = 200, items[:100] if repeated else items[(page - 1) * 100:page * 100]
      return code, {}, body if isinstance(body, bytes) else ports.canonical(body)
    with patch.object(data, "http", side_effect=http):
      return data.package_inventory(work, data.settings(self.project), complete)

  def record(self, **overrides):
    return {"id": 1, "name": "base", "type": "container", "version": "stage-fixture",
            "owner": self.state()["namespace"], "repository": None} | overrides

  def test_empty_unlinked_linked_and_multiversion_evidence(self):
    self.assertEqual(self.check(), {"base": "absent", "npm": "absent"})
    self.assertEqual(self.check({"base": [self.record()]}), {"base": "unlinked", "npm": "absent"})
    records = [self.record(id=i + 1, version="v" + str(i), repository=self.state()["repository"])
               for i in range(101)]
    self.assertEqual(self.check({"base": records})["base"], "linked")

  def test_identity_and_status_fields_are_strict(self):
    state = self.state()
    for route, source, fields in (
        ("/api/v1/user", state["principal"], ("id", "login", "active", "restricted", "prohibit_login", "type")),
        ("/api/v1/users/dev", state["namespace"], ("id", "login", "active", "restricted", "prohibit_login", "type")),
        ("/api/v1/repos/dev/dev-docker", state["repository"], ("id", "full_name", "owner", "has_packages", "permissions"))):
      for field in fields:
        for replacement in (None, "true", 1, 0, True, False):
          body = copy.deepcopy(source)
          body[field] = replacement
          if body == source and type(replacement) is type(source[field]):
            continue
          if field == "id" and type(replacement) is int and replacement > 0:
            continue  # The initial target repository ID is captured, not hard-coded.
          with self.subTest(route=route, field=field, replacement=replacement):
            self.assertRaises(ports.Refusal, self.check, responses={route: (200, body)})
        body = copy.deepcopy(source)
        body.pop(field)
        with self.subTest(route=route, missing=field):
          self.assertRaises(ports.Refusal, self.check, responses={route: (200, body)})
    repo = copy.deepcopy(state["repository"])
    for admin in (None, 1, "true", False):
      repo["permissions"] = {"admin": admin}
      self.assertRaises(ports.Refusal, self.check, responses={"/api/v1/repos/dev/dev-docker": (200, repo)})
    self.assertRaises(ports.Refusal, self.check, responses={"/api/v1/user": (200, state["principal"] | {"type": "Organization"})})

  def test_package_record_identity_and_repository_fields_are_strict(self):
    bad = [self.record(id=True), self.record(id=0), self.record(name="android"), self.record(type="npm"),
           self.record(version=""), self.record(owner={"id": True, "login": "dev"}),
           self.record(owner={"id": 7, "login": "other"}), self.record(repository={}),
           self.record(repository={"id": 20, "full_name": "dev/other"})]
    missing = self.record()
    missing.pop("repository")
    bad.append(missing)
    for record in bad:
      with self.subTest(record=record):
        self.assertRaises(ports.Refusal, self.check, {"base": [record]})

  def test_listing_errors_never_become_absence(self):
    route = "/api/v1/packages/dev/container/base"
    for response in ((201, []), (401, []), (403, []), (200, {}), (200, None), (200, b"not json"),
                     (200, b'[{"id":1,"id":2}]'), (200, [self.record()] * 101)):
      with self.subTest(response=str(response)[:80]):
        self.assertRaises((ports.Refusal, ValueError), self.check, responses={route: response})
    self.assertIsNone(ports.INVENTORY_BUDGET)

  def test_initial_404_requires_independent_complete_owner_search(self):
    responses = {"/api/v1/packages/dev/container/base": (404, b"not absence evidence")}
    self.assertEqual(self.check(responses=responses), {"base": "absent", "npm": "absent"})
    neighbors = [self.record(id=i + 1, name="base-tools", version="v" + str(i)) for i in range(101)]
    self.assertEqual(self.check(responses=responses, owner_records=neighbors)["base"], "absent")
    # Identical version strings on different packages are valid owner-search results.
    neighbors = [self.record(name="base-one"), self.record(id=2, name="base-two")]
    self.assertEqual(self.check(responses=responses, owner_records=neighbors)["base"], "absent")

  def test_owner_search_exact_target_on_later_page_is_contradictory(self):
    records = [self.record(id=i + 1, name="base-tools", version="v" + str(i)) for i in range(100)]
    for name in ("base", "BASE"):
      with self.subTest(name=name):
        self.assertRaisesRegex(ports.Refusal, "HTTP 404.*owner inventory contains it", self.check,
          responses={"/api/v1/packages/dev/container/base": (404, [])},
          owner_records=records + [self.record(id=101, name=name)])

  def test_owner_search_invalid_records_and_duplicate_identities_refuse(self):
    responses = {"/api/v1/packages/dev/container/base": (404, [])}
    neighbor = self.record(name="base-tools")
    cases = [[neighbor | {field: value}] for field, value in (
      ("id", True), ("id", 0), ("name", ""), ("name", "other"), ("type", "npm"),
      ("owner", {"id": True, "login": "dev"}), ("owner", {"id": 8, "login": "dev"}),
      ("owner", {"id": 7, "login": "other"}), ("version", ""))]
    cases += [[neighbor, neighbor], [neighbor, neighbor | {"name": "base-other"}],
              [neighbor, neighbor | {"id": 2}], [neighbor, neighbor | {"id": 2, "version": "STAGE-FIXTURE"}]]
    for field in ("owner", "repository", "name", "type", "version", "id"):
      incomplete = neighbor.copy()
      incomplete.pop(field)
      cases.append([incomplete])
    for records in cases:
      with self.subTest(records=records):
        self.assertRaises(ports.Refusal, self.check, responses=responses, owner_records=records)

  def test_owner_search_errors_and_incomplete_pages_never_prove_absence(self):
    route = "/api/v1/packages/dev"
    named = {"/api/v1/packages/dev/container/base": (404, [])}
    for response in ((201, []), (401, []), (403, []), (404, []), (500, []), (200, {}), (200, None),
                     (200, b"not json"), (200, b'[{"id":1,"id":2}]'), (200, [self.record()] * 101)):
      with self.subTest(response=str(response)[:80]):
        self.assertRaises((ports.Refusal, ValueError), self.check, responses=named | {route: response})
    neighbor = self.record(name="base-tools")
    self.assertRaisesRegex(ports.Refusal, "pagination repeated", self.check, responses=named,
                           owner_records=[neighbor], repeated=True)
    for response in ((404, []), (200, {})):
      self.assertRaises(ports.Refusal, self.check,
                        responses=named | {(route, 2): response}, owner_records=[neighbor])
    self.assertIsNone(ports.INVENTORY_BUDGET)

  def test_later_exact_404_does_not_use_owner_search(self):
    self.assertRaisesRegex(ports.Refusal, "HTTP 404", self.check, {"base": [self.record()]},
      responses={("/api/v1/packages/dev/container/base", 2): (404, []),
                 "/api/v1/packages/dev": (200, [])})

  def test_completed_404_with_verified_absence_still_refuses(self):
    self.assertRaisesRegex(ports.Refusal, "Required package association missing", self.check, complete=True,
      responses={"/api/v1/packages/dev/container/base": (404, [])})

  def test_duplicate_repeated_and_inconsistent_versions_refuse(self):
    first = self.record()
    cases = [[first, first], [first, self.record(id=2)],
             [first, self.record(id=2, version="other", repository=self.state()["repository"])]]
    for records in cases:
      with self.subTest(records=records):
        self.assertRaises(ports.Refusal, self.check, {"base": records})
    self.assertRaisesRegex(ports.Refusal, "pagination repeated", self.check, {"base": [first]}, repeated=True)
    self.assertIsNone(ports.INVENTORY_BUDGET)

  def test_completed_missing_or_unlinked_packages_refuse(self):
    self.assertRaises(ports.Refusal, self.check, complete=True)
    self.assertRaises(ports.Refusal, self.check, {"base": [self.record()]}, complete=True)

  def test_link_prerequisite_read_failure_never_attempts_a_post(self):
    with patch.object(data, "guard", side_effect=ports.CommandFailed("Read failed")), patch.object(data, "http") as http:
      with self.assertRaises(ports.Refusal) as error:
        data.link_package(self.project, self.root, {}, "base")
      self.assertNotIsInstance(error.exception, ports.CommandFailed)
      http.assert_not_called()

  def test_package_nonterminal_inventory_stops_at_page_budget(self):
    authority = {"owner": "dev", "owner_id": 7, "repository_id": 19, "repository": "dev/dev-docker"}
    def read_page(work, config, *segments, query):
      return 200, {}, ports.canonical([self.record(id=query["page"], version="page-" + str(query["page"]))])
    with patch.object(data, "api_response", side_effect=read_page) as reader:
      with self.assertRaisesRegex(ports.Refusal, "no terminal empty page"):
        data.package_association(self.root, {}, authority, "base")
      self.assertEqual(reader.call_count, 1002)

  def test_fallback_shares_page_and_item_budgets_with_exact_inventory(self):
    authority = {"owner": "dev", "owner_id": 7, "repository_id": 19, "repository": "dev/dev-docker"}
    config = data.settings(self.project)
    for budget, expected, calls in (
        ({"pages": 1001}, "page budget exceeded", 1),
        ({"items": 100000}, "item budget exceeded", 2)):
      def response(work, config, *segments, query):
        if len(segments) == 4:
          return 404, {}, b""
        return 200, {}, ports.canonical([self.record(name="base-tools")])
      with self.subTest(budget=budget), patch.object(ports, "INVENTORY_BUDGET", budget), \
           patch.object(data, "api_response", side_effect=response) as reader:
        self.assertRaisesRegex(ports.Refusal, expected, data.package_association, self.root, config, authority, "base")
        self.assertEqual(reader.call_count, calls)

  def test_fallback_nonterminal_inventory_stops_at_page_budget(self):
    authority = {"owner": "dev", "owner_id": 7, "repository_id": 19, "repository": "dev/dev-docker"}
    def read_page(work, config, *segments, query):
      return [self.record(id=query["page"], name="base-tools", version="page-" + str(query["page"]))]
    with patch.object(data, "api_read", side_effect=read_page) as reader:
      self.assertRaisesRegex(ports.Refusal, "no terminal empty page", data.verify_package_absent,
                             self.root, data.settings(self.project), authority, "base")
      self.assertEqual(reader.call_count, 1002)

  def test_fallback_real_transport_enforces_shared_byte_and_time_budgets(self):
    authority = {"owner": "dev", "owner_id": 7, "repository_id": 19, "repository": "dev/dev-docker"}
    for budget, expected in (
        ({"deadline": 0, "bytes": 0}, "Inventory time budget exceeded"),
        ({"deadline": time.monotonic() + 60, "bytes": 64 * 1024 * 1024}, "Inventory byte/time budget exceeded")):
      packet = (0, {"stdout": b"200", "stderr": b"", "headers": b"", "body": b"[]"})
      with self.subTest(budget=budget), patch.object(ports, "INVENTORY_BUDGET", budget), \
           patch.object(ports, "capture", return_value=packet) as capture:
        self.assertRaisesRegex(ports.Refusal, expected, data.verify_package_absent,
                               self.root, data.settings(self.project), authority, "base")
        self.assertEqual(capture.call_count, 0 if budget["deadline"] == 0 else 1)
