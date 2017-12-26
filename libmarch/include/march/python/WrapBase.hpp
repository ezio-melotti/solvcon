#pragma once

/*
 * Copyright (c) 2017, Yung-Yu Chen <yyc@solvcon.net>
 * BSD 3-Clause License, see COPYING
 */

#include <pybind11/pybind11.h>

#include <memory>

#ifdef __GNUG__
#  define MARCH_PYTHON_WRAPPER_VISIBILITY __attribute__((visibility("hidden")))
#else
#  define MARCH_PYTHON_WRAPPER_VISIBILITY
#endif

namespace march {

namespace python {

/**
 * Helper class for pybind11 class wrappers.
 */
template< class Wrapper, class Wrapped, class Holder = std::unique_ptr<Wrapped> >
class
MARCH_PYTHON_WRAPPER_VISIBILITY
WrapBase {

public:

    using wrapper_type = Wrapper;
    using wrapped_type = Wrapped;
    using holder_type = Holder;
    using base_type = WrapBase< wrapper_type, wrapped_type, holder_type >;

    static wrapper_type & commit(pybind11::module & mod, const char * pyname, const char * clsdoc) {
        static wrapper_type derived(mod, pyname, clsdoc);
        return derived;
    }

    WrapBase() = delete;
    WrapBase(WrapBase const & ) = default;
    WrapBase(WrapBase       &&) = delete;
    WrapBase & operator=(WrapBase const & ) = default;
    WrapBase & operator=(WrapBase       &&) = delete;

#define DECL_MARCH_PYBIND_CLASS_METHOD(METHOD) \
    template< class... Args > \
    wrapper_type & METHOD(Args&&... args) { \
        m_cls.METHOD(std::forward<Args>(args)...); \
        return *static_cast<wrapper_type*>(this); \
    }

    DECL_MARCH_PYBIND_CLASS_METHOD(def)
    DECL_MARCH_PYBIND_CLASS_METHOD(def_property)
    DECL_MARCH_PYBIND_CLASS_METHOD(def_property_readonly)
    DECL_MARCH_PYBIND_CLASS_METHOD(def_property_readonly_static)

#undef DECL_MARCH_PYBIND_CLASS_METHOD

protected:

    WrapBase(pybind11::module & mod, const char * pyname, const char * clsdoc)
        : m_cls(pybind11::class_< wrapped_type, holder_type >(mod, pyname, clsdoc))
    {}

    pybind11::class_< wrapped_type, holder_type > m_cls;

}; /* end class WrapBase */

} /* end namespace python */

} /* end namespace march */

// vim: set ff=unix fenc=utf8 nobomb et sw=4 ts=4:
