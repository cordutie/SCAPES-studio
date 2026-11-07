// Every audio parameter of an effect moves to its new value in a few milliseconds instead of at once, so a knob that is
// turned fast does not click. One place for the time: change GLIDE_S to make all the effects slower or faster.
export const GLIDE_S = 0.012;                       // time constant: the value is 90 % there after 2.3 x this
export const glide = (actx, param, value) => param.setTargetAtTime(value, actx.currentTime, GLIDE_S);
