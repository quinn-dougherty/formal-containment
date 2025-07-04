import Aesop
import Imp
open Imp

theorem my_hoare_triple : {{astn x > y}}(
imp {
  x := y;
}
){{astn x <= y}} := by
  simp
  intros σ σ' h1 h2
  cases h2 with
  | assign h2_eq =>
    simp [Env.set]
    simp [Expr.eval, Env.get] at h2_eq
    subst h2_eq
    apply Int.le_refl
