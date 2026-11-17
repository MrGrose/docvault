Feature: HITL evidence and review
  Agent run не публикует поддельную цитату; слабый claim идет в human review.

  Scenario: Fabricated quote is rejected
    Given an empty repository
    And a source blob "tariff 100" as ref
    When I create a run claiming quote "tariff 999"
    Then the run is ungrounded

  Scenario: Weak claim needs human then accept publishes
    Given an empty repository
    And a source blob "alpha beta warehouse" as ref
    When I create a run with unrelated claim text
    Then the run status is needs_human
    When I accept the run with idempotency key "bdd-accept-1"
    Then the run is published