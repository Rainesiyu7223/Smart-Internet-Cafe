(define (domain cybercafe)
  (:requirements :strips)
  (:predicates
    (seat ?s)
    (is-clean ?s)
    (is-quiet ?s)
    (is-bright ?s)
    (is-available ?s)
    (recommended ?s)
  )

  (:action recommend-perfect-seat
    :parameters (?s)
    :precondition (and (seat ?s) (is-available ?s) (is-clean ?s) (is-quiet ?s) (is-bright ?s))
    :effect (recommended ?s)
  )
)