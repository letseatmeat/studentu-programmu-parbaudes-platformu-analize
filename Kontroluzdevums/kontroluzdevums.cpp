#include <iostream>
#include <iomanip>
#include <memory>
#include <string>
#include <vector>

class AssessmentItem {
private:
    std::string name;
    double basePoints;

protected:
    double getBasePoints() const {
        return basePoints;
    }

public:
    AssessmentItem(const std::string& itemName, double points)
        : name(itemName), basePoints(points) {}

    virtual ~AssessmentItem() = default;

    std::string getName() const {
        return name;
    }

    virtual std::string category() const = 0;
    virtual double score() const = 0;
};

class LabWork : public AssessmentItem {
private:
    double qualityFactor;

public:
    LabWork(const std::string& itemName, double points, double factor)
        : AssessmentItem(itemName, points), qualityFactor(factor) {}

    std::string category() const override {
        return "LAB";
    }

    double score() const override {
        return getBasePoints() * qualityFactor;
    }
};

class ExamTask : public AssessmentItem {
private:
    int solvedTests;
    int totalTests;

public:
    ExamTask(const std::string& itemName, double points, int solved, int total)
        : AssessmentItem(itemName, points), solvedTests(solved), totalTests(total) {}

    std::string category() const override {
        return "EXAM";
    }

    double score() const override {
        return getBasePoints() * solvedTests / totalTests;
    }
};

int main() {
    std::vector<std::unique_ptr<AssessmentItem>> items;

    items.push_back(std::make_unique<LabWork>("encapsulation", 10.0, 0.8));
    items.push_back(std::make_unique<LabWork>("inheritance", 15.0, 0.6));
    items.push_back(std::make_unique<ExamTask>("polymorphism", 20.0, 9, 10));

    double totalScore = 0.0;
    int polymorphicCalls = 0;

    std::string categorySequence;

    for (const auto& item : items) {
        totalScore += item->score();
        polymorphicCalls++;

        if (!categorySequence.empty()) {
            categorySequence += ",";
        }

        categorySequence += item->category();
    }

    std::cout << "OOP_TEST_START\n";
    std::cout << "abstract_base_class=1\n";
    std::cout << "encapsulated_objects=" << items.size() << "\n";
    std::cout << "derived_class_types=2\n";
    std::cout << "polymorphic_calls=" << polymorphicCalls << "\n";
    std::cout << "category_sequence=" << categorySequence << "\n";
    std::cout << "total_score=" << std::fixed << std::setprecision(2) << totalScore << "\n";
    std::cout << "OOP_TEST_END\n";

    return 0;
}
