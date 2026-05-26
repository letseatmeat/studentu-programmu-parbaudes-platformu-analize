#ifndef BUS_ROUTES_REFERENCE_TESTS_H
#define BUS_ROUTES_REFERENCE_TESTS_H

#include <cxxtest/TestSuite.h>

#include <algorithm>
#include <cctype>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <sstream>
#include <streambuf>
#include <string>
#include <vector>

int main();

class BusRoutesReferenceTests : public CxxTest::TestSuite
{
public:
    struct RunResult
    {
        int returnCode;
        std::string stdoutText;
        std::string errTxtText;
    };

    void test_a_route()
    {
        RunResult r = runProgram("a\nRiga\nKraslava\ne\n");

        TS_ASSERT(returnCodeOk(r.returnCode));
        TS_ASSERT(hasSeparateResultLine(r.stdoutText));

        std::vector<std::string> expected;
        expected.push_back("Riga Kraslava Pr 15:00 11.00");
        expected.push_back("Riga Kraslava Pr 18:00 11.00");

        assertContainsSequence(normalizeOutput(r.stdoutText, false), expected, "test_a_route");
    }

    void test_b_day()
    {
        RunResult r = runProgram("b\nPt\ne\n");

        TS_ASSERT(returnCodeOk(r.returnCode));
        TS_ASSERT(hasSeparateResultLine(r.stdoutText));

        std::vector<std::string> expected;
        expected.push_back("Riga Ventspils Pt 09:00 6.70");
        expected.push_back("Liepaja Ventspils Pt 17:00 5.50");

        assertContainsSequence(normalizeOutput(r.stdoutText, false), expected, "test_b_day");
    }

    void test_c_price()
    {
        RunResult r = runProgram("c\n5.90\ne\n");

        TS_ASSERT(returnCodeOk(r.returnCode));
        TS_ASSERT(hasSeparateResultLine(r.stdoutText));

        std::vector<std::string> expected;
        expected.push_back("Kraslava Daugavpils Ot 10:00 3.00");
        expected.push_back("Dagda Kraslava Ce 18:00 2.50");
        expected.push_back("Liepaja Ventspils Pt 17:00 5.50");

        assertContainsSequence(normalizeOutput(r.stdoutText, false), expected, "test_c_price");
    }

    void test_d_errtxt()
    {
        RunResult r = runProgram("d\ne\n");

        TS_ASSERT(returnCodeOk(r.returnCode));
        TS_ASSERT(hasSeparateResultLine(r.stdoutText));

        std::vector<std::string> expected;
        expected.push_back("Ventsplis,8.00,Liepaja,Sv,20:00");
        expected.push_back("Dagda,Sv");
        expected.push_back("Dagda,Kraslava,Ce,18:00,2.50,Sv");

        std::vector<std::string> outLines = normalizeOutput(r.stdoutText, true);
        if (containsExpectedSequence(outLines, expected))
        {
            TS_ASSERT(true);
            return;
        }

        std::vector<std::string> errLines = normalizeOutput(r.errTxtText, true);
        assertContainsSequence(errLines, expected, "test_d_errtxt");
    }

private:
    static bool returnCodeOk(int rc)
    {
        return rc == 0 || rc == 1;
    }

    static std::string trim(const std::string& s)
    {
        std::size_t start = 0;
        while (start < s.size() && std::isspace(static_cast<unsigned char>(s[start])))
        {
            ++start;
        }

        std::size_t end = s.size();
        while (end > start && std::isspace(static_cast<unsigned char>(s[end - 1])))
        {
            --end;
        }

        return s.substr(start, end - start);
    }

    static std::string collapseSpaces(const std::string& s)
    {
        std::string t = trim(s);
        std::string out;
        bool inSpace = false;

        for (std::size_t i = 0; i < t.size(); ++i)
        {
            unsigned char ch = static_cast<unsigned char>(t[i]);
            if (std::isspace(ch))
            {
                if (!inSpace)
                {
                    out += ' ';
                    inSpace = true;
                }
            }
            else
            {
                out += static_cast<char>(ch);
                inSpace = false;
            }
        }

        return out;
    }

    static std::string stripAllWs(const std::string& s)
    {
        std::string out;
        for (std::size_t i = 0; i < s.size(); ++i)
        {
            unsigned char ch = static_cast<unsigned char>(s[i]);
            if (!std::isspace(ch))
            {
                out += static_cast<char>(ch);
            }
        }
        return out;
    }

    static std::vector<std::string> normalizeOutput(const std::string& text, bool csvMode)
    {
        std::vector<std::string> lines;
        std::stringstream ss(text);
        std::string line;

        while (std::getline(ss, line))
        {
            std::string t = trim(line);
            if (t.empty())
            {
                continue;
            }

            if (csvMode)
            {
                lines.push_back(stripAllWs(t));
            }
            else
            {
                lines.push_back(collapseSpaces(t));
            }
        }

        return lines;
    }

    static bool containsExpectedSequence(
        const std::vector<std::string>& actual,
        const std::vector<std::string>& expected)
    {
        std::size_t idx = 0;
        for (std::size_t i = 0; i < actual.size(); ++i)
        {
            if (idx < expected.size() && actual[i] == expected[idx])
            {
                ++idx;
            }
        }
        return idx == expected.size();
    }

    static void assertContainsSequence(
        const std::vector<std::string>& actual,
        const std::vector<std::string>& expected,
        const std::string& testName)
    {
        if (containsExpectedSequence(actual, expected))
        {
            TS_ASSERT(true);
            return;
        }

        std::ostringstream msg;
        msg << testName << " failed. Expected sequence was not found.\nExpected:\n";
        for (std::size_t i = 0; i < expected.size(); ++i)
        {
            msg << expected[i] << "\n";
        }
        msg << "Actual normalized output:\n";
        for (std::size_t i = 0; i < actual.size(); ++i)
        {
            msg << actual[i] << "\n";
        }

        TS_FAIL(msg.str());
    }

    static bool hasSeparateResultLine(const std::string& text)
    {
        std::stringstream ss(text);
        std::string line;
        while (std::getline(ss, line))
        {
            if (stripAllWs(line) == "result:")
            {
                return true;
            }
        }
        return false;
    }

    static std::string readWholeFile(const std::string& path)
    {
        std::ifstream in(path.c_str(), std::ios::in | std::ios::binary);
        if (!in)
        {
            return std::string();
        }

        std::ostringstream buf;
        buf << in.rdbuf();
        return buf.str();
    }

    static RunResult runProgram(const std::string& input)
    {
        std::remove("err.txt");

        std::istringstream fakeIn(input);
        std::ostringstream fakeOut;

        std::streambuf* oldCin = std::cin.rdbuf(fakeIn.rdbuf());
        std::streambuf* oldCout = std::cout.rdbuf(fakeOut.rdbuf());

        int rc = 0;
        try
        {
            rc = ::main();
        }
        catch (...)
        {
            std::cin.rdbuf(oldCin);
            std::cout.rdbuf(oldCout);
            TS_FAIL("The student program threw an exception.");
        }

        std::cin.rdbuf(oldCin);
        std::cout.rdbuf(oldCout);

        RunResult result;
        result.returnCode = rc;
        result.stdoutText = fakeOut.str();
        result.errTxtText = readWholeFile("err.txt");
        return result;
    }
};

#endif
